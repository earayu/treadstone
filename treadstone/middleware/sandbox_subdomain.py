"""
ASGI middleware for subdomain-based sandbox routing.

When sandbox_domain is configured (e.g. "treadstone-ai.dev"), requests to
  sandbox-{name}.treadstone-ai.dev
are transparently proxied to the corresponding sandbox pod, supporting
both HTTP and WebSocket.

Only subdomains that start with ``sandbox_subdomain_prefix`` (default
``sandbox-``) are intercepted; all other hosts pass through unchanged.
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


def extract_sandbox_name(host: str, sandbox_domain: str, prefix: str = "sandbox-") -> str | None:
    """Return the sandbox name from a Host header, or None.

    "sandbox-foobar.treadstone-ai.dev" with domain "treadstone-ai.dev"
    → returns "foobar"

    Only subdomains that start with *prefix* are recognised.  Subdomains
    like "api.treadstone-ai.dev" or "www.treadstone-ai.dev" are ignored
    because they don't carry the prefix.
    """
    host_no_port = host.split(":")[0].lower()
    domain = sandbox_domain.lower()

    if not host_no_port.endswith(f".{domain}"):
        return None

    subdomain = host_no_port[: -(len(domain) + 1)]
    if not subdomain or "." in subdomain:
        return None
    if not subdomain.startswith(prefix):
        return None
    name = subdomain[len(prefix) :]
    return name if name else None


class SandboxSubdomainMiddleware:
    """ASGI middleware that intercepts requests to {prefix}*.sandbox_domain and proxies them."""

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
        sandbox_name = (
            extract_sandbox_name(host, settings.sandbox_domain, settings.sandbox_subdomain_prefix) if host else None
        )

        if sandbox_name is None:
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            await self._handle_http(scope, receive, send, sandbox_name)
        else:
            await self._handle_websocket(scope, receive, send, sandbox_name)

    @staticmethod
    def _get_host(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == b"host":
                return value.decode("latin-1")
        return None

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send, sandbox_name: str) -> None:
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
        target_url = build_sandbox_url(sandbox_name, full_path)
        logger.info("Subdomain proxy %s %s → %s", request.method, sandbox_name, target_url)

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

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send, sandbox_name: str) -> None:
        websocket = WebSocket(scope, receive, send)
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("latin-1")
        if query_string:
            path = f"{path}?{query_string}"
        logger.info("Subdomain WS proxy %s → %s", sandbox_name, path)

        await websocket.accept()

        try:
            await proxy_websocket(
                client_ws=websocket,
                sandbox_id=sandbox_name,
                path=path,
            )
        except Exception:
            try:
                await websocket.close(code=1011, reason="upstream connection failed")
            except RuntimeError:
                pass
