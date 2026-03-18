"""
Transparent reverse proxy to Sandbox pods running in Kubernetes.

Replaces the upstream sandbox-router
(https://github.com/kubernetes-sigs/agent-sandbox/blob/main/clients/python/agentic-sandbox-client/sandbox-router/sandbox_router.py)
with a first-party implementation that also supports WebSocket proxying.

The API contract is intentionally compatible with the official sandbox-router so
that the k8s-agent-sandbox Python SDK can target this service as well.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

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


def _sanitize_namespace(namespace: str) -> bool:
    return namespace.replace("-", "").replace("_", "").isalnum()


def _sanitize_sandbox_id(sandbox_id: str) -> bool:
    return sandbox_id.replace("-", "").replace("_", "").isalnum()


def _filter_request_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove hop-by-hop headers and force identity encoding."""
    filtered = {k: v for k, v in headers.items() if k.lower() not in PROXY_HOP_HEADERS}
    filtered["accept-encoding"] = "identity"
    return filtered


def _filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Keep content headers, strip hop-by-hop."""
    return {k: v for k, v in headers.multi_items() if k.lower() not in PROXY_HOP_HEADERS}


def resolve_routing(
    headers: dict[str, str],
    *,
    path_sandbox_id: str | None = None,
) -> dict[str, Any]:
    """Resolve sandbox routing from path params (priority) and/or headers.

    Defaults for namespace and port come from settings, overridable per-request
    via X-Sandbox-Namespace / X-Sandbox-Port headers.

    Returns a dict with sandbox_id, namespace, port.
    Raises ValueError for invalid input.
    """
    sandbox_id = path_sandbox_id or headers.get("x-sandbox-id")
    if not sandbox_id:
        raise ValueError("X-Sandbox-ID header is required.")
    if not _sanitize_sandbox_id(sandbox_id):
        raise ValueError("Invalid sandbox ID format.")

    namespace = headers.get("x-sandbox-namespace", settings.sandbox_namespace)
    if not _sanitize_namespace(namespace):
        raise ValueError("Invalid namespace format.")

    port_raw = headers.get("x-sandbox-port", str(settings.sandbox_port))
    try:
        port = int(port_raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid port format.") from exc

    return {"sandbox_id": sandbox_id, "namespace": namespace, "port": port}


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
    logger.info("Proxying %s to %s", method, target_url)

    client = await get_http_client()
    outgoing = _filter_request_headers(headers)

    req = client.build_request(method=method, url=target_url, headers=outgoing, content=body)
    resp = await client.send(req, stream=True)

    resp_headers = _filter_response_headers(resp.headers)
    return resp.status_code, resp_headers, resp


async def proxy_websocket(
    *,
    client_ws: WebSocket,
    sandbox_id: str,
    path: str,
    namespace: str | None = None,
    port: int | None = None,
) -> None:
    """Bidirectional WebSocket proxy between the client and a sandbox pod."""
    target_url = build_sandbox_url(sandbox_id, path, namespace=namespace, port=port, scheme="ws")
    logger.info("WS proxy to %s", target_url)

    async with websockets.asyncio.client.connect(target_url) as upstream:

        async def client_to_upstream() -> None:
            try:
                while True:
                    data = await client_ws.receive_bytes()
                    await upstream.send(data)
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

        done, pending = await asyncio.wait(
            [asyncio.create_task(client_to_upstream()), asyncio.create_task(upstream_to_client())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
