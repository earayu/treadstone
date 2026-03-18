"""
ASGI middleware for subdomain-based sandbox routing.

When sandbox_domain is configured (e.g. "sandbox.localhost"), requests to
  {sandbox_id}.sandbox.localhost
are transparently proxied to the corresponding sandbox pod, supporting
both HTTP and WebSocket.

Requests to other hosts pass through to the normal FastAPI app unchanged.
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import Response, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

from treadstone.config import settings
from treadstone.services.sandbox_proxy import (
    _filter_request_headers,
    _filter_response_headers,
    build_sandbox_url,
    get_http_client,
    proxy_websocket,
)

logger = logging.getLogger(__name__)


def extract_sandbox_id(host: str, sandbox_domain: str) -> str | None:
    """Extract sandbox_id from Host header.

    "sb-123.sandbox.localhost:8000" with domain "sandbox.localhost"
    → returns "sb-123"
    """
    host_no_port = host.split(":")[0].lower()
    domain = sandbox_domain.lower()

    if not host_no_port.endswith(f".{domain}"):
        return None

    prefix = host_no_port[: -(len(domain) + 1)]
    if not prefix or "." in prefix:
        return None
    return prefix


class SandboxSubdomainMiddleware:
    """ASGI middleware that intercepts requests to *.sandbox_domain and proxies them."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not settings.sandbox_domain:
            await self.app(scope, receive, send)
            return

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        host = self._get_host(scope)
        sandbox_id = extract_sandbox_id(host, settings.sandbox_domain) if host else None

        if sandbox_id is None:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            await self._handle_http(scope, receive, send, sandbox_id)
        else:
            await self._handle_websocket(scope, receive, send, sandbox_id)

    @staticmethod
    def _get_host(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == b"host":
                return value.decode("latin-1")
        return None

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send, sandbox_id: str) -> None:
        request = Request(scope, receive)
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("latin-1")
        headers = dict(request.headers)

        body_parts: list[bytes] = []
        while True:
            message = await receive()
            body_parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(body_parts)

        full_path = f"{path}?{query_string}" if query_string else path
        target_url = build_sandbox_url(sandbox_id, full_path)
        logger.info("Subdomain proxy %s %s → %s", request.method, sandbox_id, target_url)

        client = await get_http_client()
        outgoing = _filter_request_headers(headers)

        try:
            req = client.build_request(method=request.method, url=target_url, headers=outgoing, content=body)
            resp = await client.send(req, stream=True)
        except Exception:
            error_resp = Response("Bad Gateway", status_code=502)
            await error_resp(scope, receive, send)
            return

        resp_headers = _filter_response_headers(resp.headers)
        streaming = StreamingResponse(
            content=resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=resp_headers,
        )
        await streaming(scope, receive, send)

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send, sandbox_id: str) -> None:
        websocket = WebSocket(scope, receive, send)
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("latin-1")
        if query_string:
            path = f"{path}?{query_string}"
        logger.info("Subdomain WS proxy %s → %s", sandbox_id, path)

        await websocket.accept()

        try:
            await proxy_websocket(
                client_ws=websocket,
                sandbox_id=sandbox_id,
                path=path,
            )
        except Exception:
            try:
                await websocket.close(code=1011, reason="upstream connection failed")
            except RuntimeError:
                pass
