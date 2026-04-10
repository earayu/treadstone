"""
Transparent reverse proxy to Sandbox pods running in Kubernetes.

Inspired by the upstream sandbox-router
(https://github.com/kubernetes-sigs/agent-sandbox/blob/main/clients/python/agentic-sandbox-client/sandbox-router/sandbox_router.py)
but implemented in-tree with WebSocket support. Routing (namespace, port,
Kubernetes service name) is decided by the API layer and settings, not by
client request headers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx
import websockets
import websockets.asyncio.client
from fastapi import WebSocket, WebSocketDisconnect

from treadstone.config import settings

logger = logging.getLogger(__name__)

PROXY_HOP_HEADERS = frozenset(
    {
        "host",
        "transfer-encoding",
        "connection",
        "keep-alive",
        "upgrade",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
    }
)


def _is_x_sandbox_vendor_header(name: str) -> bool:
    """True if the header is in the legacy X-Sandbox-* family; never forward to the workload."""
    return name.lower().startswith("x-sandbox")


def _build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.sandbox_proxy_timeout)


_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = _build_http_client()
    return _http_client


async def close_http_client() -> None:
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


def build_sandbox_url(
    sandbox_id: str,
    path: str,
    *,
    namespace: str | None = None,
    port: int | None = None,
    scheme: str = "http",
) -> str:
    ns = namespace or settings.sandbox_namespace
    p = port or settings.sandbox_port
    host = f"{sandbox_id}.{ns}.svc.cluster.local"
    return f"{scheme}://{host}:{p}/{path.lstrip('/')}"


def _filter_request_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop headers, X-Sandbox-* (any suffix), and force identity encoding."""
    filtered = {
        k: v for k, v in headers.items() if k.lower() not in PROXY_HOP_HEADERS and not _is_x_sandbox_vendor_header(k)
    }
    filtered["accept-encoding"] = "identity"
    return filtered


def _filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Keep content headers, strip hop-by-hop."""
    return {k: v for k, v in headers.multi_items() if k.lower() not in PROXY_HOP_HEADERS}


async def proxy_http_request(
    *,
    method: str,
    sandbox_id: str,
    path: str,
    headers: dict[str, str],
    body: bytes,
    namespace: str | None = None,
    port: int | None = None,
) -> tuple[int, dict[str, str], httpx.Response]:
    """Proxy an HTTP request to a sandbox pod and return (status, headers, streaming response)."""
    target_url = build_sandbox_url(sandbox_id, path, namespace=namespace, port=port)
    logger.debug("Proxying %s to %s", method, target_url)

    client = await get_http_client()
    outgoing = _filter_request_headers(headers)

    req = client.build_request(method=method, url=target_url, headers=outgoing, content=body)
    resp = await client.send(req, stream=True)

    resp_headers = _filter_response_headers(resp.headers)
    return resp.status_code, resp_headers, resp


WS_ACTIVITY_TOUCH_INTERVAL = 30
"""Seconds between periodic ``gmt_last_active`` touches during a WebSocket
session.  Chosen to be well below the minimum ``auto_stop_interval`` of
1 minute so even the shortest idle threshold cannot fire while the
connection is alive, while keeping DB traffic to ~2 writes/min per
connection."""


async def proxy_websocket(
    *,
    client_ws: WebSocket,
    sandbox_id: str,
    path: str,
    namespace: str | None = None,
    port: int | None = None,
    on_activity: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Bidirectional WebSocket proxy between the client and a sandbox pod.

    *on_activity* is called once when the upstream connection is established
    and then every ``WS_ACTIVITY_TOUCH_INTERVAL`` seconds while the relay
    is running.  Callers use it to bump ``gmt_last_active`` so long-lived
    sessions prevent idle auto-stop.  Failures in the callback are logged
    but never tear down the WebSocket session.
    """
    target_url = build_sandbox_url(sandbox_id, path, namespace=namespace, port=port, scheme="ws")
    logger.debug("WS proxy to %s", target_url)

    async with websockets.asyncio.client.connect(target_url) as upstream:
        if on_activity is not None:
            try:
                await on_activity()
            except Exception:
                logger.debug("Initial activity touch failed for WS proxy to %s", sandbox_id)

        async def client_to_upstream() -> None:
            try:
                while True:
                    msg = await client_ws.receive()
                    if "bytes" in msg and msg["bytes"]:
                        await upstream.send(msg["bytes"])
                    elif "text" in msg and msg["text"]:
                        await upstream.send(msg["text"])
                    else:
                        break
            except WebSocketDisconnect:
                pass

        async def upstream_to_client() -> None:
            try:
                async for msg in upstream:
                    if isinstance(msg, bytes):
                        await client_ws.send_bytes(msg)
                    else:
                        await client_ws.send_text(msg)
            except websockets.exceptions.ConnectionClosed:
                pass

        async def periodic_activity_touch() -> None:
            """Periodically refresh gmt_last_active so the sandbox is not
            mistaken for idle during a long-lived WebSocket session."""
            try:
                while True:
                    await asyncio.sleep(WS_ACTIVITY_TOUCH_INTERVAL)
                    if on_activity is not None:
                        try:
                            await on_activity()
                        except Exception:
                            logger.debug("Periodic activity touch failed for WS proxy to %s", sandbox_id)
            except asyncio.CancelledError:
                pass

        done, pending = await asyncio.wait(
            [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
                asyncio.create_task(periodic_activity_touch()),
            ],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
