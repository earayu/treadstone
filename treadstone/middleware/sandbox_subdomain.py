"""
ASGI middleware for authenticated subdomain-based sandbox routing.

When sandbox_domain is configured (e.g. "treadstone-ai.dev"), requests to
  sandbox-{sandbox_id}.treadstone-ai.dev
are authenticated at the edge and then transparently proxied to the
corresponding sandbox pod, supporting both HTTP and WebSocket.
"""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie
from urllib.parse import urlencode

from sqlalchemy import select, update
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket

from treadstone.config import settings
from treadstone.core.database import async_session
from treadstone.core.request_context import set_request_context, set_scope_context
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import utc_now
from treadstone.services.audit import record_audit_event
from treadstone.services.browser_auth import (
    SANDBOX_WEB_COOKIE_NAME,
    SANDBOX_WEB_COOKIE_TTL_SECONDS,
    issue_sandbox_web_cookie,
    verify_bootstrap_ticket,
    verify_sandbox_web_cookie,
)
from treadstone.services.sandbox_proxy import (
    _filter_request_headers,
    _filter_response_headers,
    build_sandbox_url,
    get_http_client,
    proxy_websocket,
)

logger = logging.getLogger(__name__)

_HTML_NOT_FOUND = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sandbox Not Found</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#09090b;color:#e4e4e7;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh}
    .card{text-align:center;max-width:440px;padding:3rem 2rem}
    .icon{font-size:2.5rem;margin-bottom:1.25rem;opacity:.35;line-height:1}
    h1{font-size:1.375rem;font-weight:600;margin-bottom:.625rem;letter-spacing:-.015em}
    p{font-size:.9rem;color:#71717a;line-height:1.65}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⬡</div>
    <h1>Sandbox Not Found</h1>
    <p>This sandbox does not exist, or the link may have expired.<br>
       If you believe this is an error, please check the sandbox ID.</p>
  </div>
</body>
</html>
"""

_HTML_STARTING = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="5">
  <title>Sandbox Starting</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#09090b;color:#e4e4e7;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh}
    .card{text-align:center;max-width:440px;padding:3rem 2rem}
    .spinner{width:36px;height:36px;border:3px solid #27272a;border-top-color:#3b82f6;
             border-radius:50%;animation:spin .9s linear infinite;margin:0 auto 1.5rem}
    @keyframes spin{to{transform:rotate(360deg)}}
    h1{font-size:1.375rem;font-weight:600;margin-bottom:.625rem;letter-spacing:-.015em}
    p{font-size:.9rem;color:#71717a;line-height:1.65}
    .hint{margin-top:.75rem;font-size:.8rem;color:#52525b}
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h1>Sandbox Starting</h1>
    <p>Your sandbox is warming up. Please wait a moment.</p>
    <p class="hint">This page refreshes automatically every 5 seconds.</p>
  </div>
</body>
</html>
"""


def _html_not_found() -> Response:
    return Response(content=_HTML_NOT_FOUND, status_code=404, media_type="text/html; charset=utf-8")


def _html_starting() -> Response:
    return Response(content=_HTML_STARTING, status_code=200, media_type="text/html; charset=utf-8")


def extract_sandbox_id(host: str, sandbox_domain: str, prefix: str = "sandbox-") -> str | None:
    host_no_port = host.split(":")[0].lower()
    domain = sandbox_domain.lower()

    if not host_no_port.endswith(f".{domain}"):
        return None

    subdomain = host_no_port[: -(len(domain) + 1)]
    if not subdomain or "." in subdomain:
        return None
    if not subdomain.startswith(prefix):
        return None
    sandbox_id = subdomain[len(prefix) :]
    return sandbox_id if sandbox_id else None


def _request_scheme(scope: Scope) -> str:
    headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
    forwarded = headers.get("x-forwarded-proto")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return str(scope.get("scheme", "http"))


def _sanitize_next_path(value: str | None) -> str:
    if not value:
        return "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def _strip_internal_auth(headers: dict[str, str]) -> dict[str, str]:
    filtered = dict(_filter_request_headers(headers))

    cookie_header = filtered.get("cookie") or filtered.get("Cookie")
    if not cookie_header:
        return filtered

    jar = SimpleCookie()
    jar.load(cookie_header)
    if SANDBOX_WEB_COOKIE_NAME in jar:
        del jar[SANDBOX_WEB_COOKIE_NAME]

    remaining = "; ".join(f"{m.key}={m.coded_value}" for m in jar.values())
    filtered.pop("cookie", None)
    filtered.pop("Cookie", None)
    if remaining:
        filtered["cookie"] = remaining
    return filtered


class SandboxSubdomainMiddleware:
    """ASGI middleware that intercepts sandbox subdomains and applies browser auth before proxying."""

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
        sandbox_id = (
            extract_sandbox_id(host, settings.sandbox_domain, settings.sandbox_subdomain_prefix) if host else None
        )
        if sandbox_id is None:
            await self.app(scope, receive, send)
            return
        set_scope_context(
            scope,
            sandbox_id=sandbox_id,
            route_kind="subdomain_ws" if scope["type"] == "websocket" else "subdomain_http",
        )

        if scope["type"] == "http":
            await self._handle_http(scope, receive, send, sandbox_id, host)
        else:
            await self._handle_websocket(scope, receive, send, sandbox_id)

    @staticmethod
    def _get_host(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == b"host":
                return value.decode("latin-1")
        return None

    async def _load_sandbox(self, sandbox_id: str) -> Sandbox | None:
        async with async_session() as session:
            result = await session.execute(
                select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.gmt_deleted.is_(None))
            )
            return result.scalar_one_or_none()

    async def _touch_last_active(self, sandbox_id: str) -> None:
        try:
            async with async_session() as session:
                await session.execute(
                    update(Sandbox)
                    .where(Sandbox.id == sandbox_id, Sandbox.gmt_deleted.is_(None))
                    .values(gmt_last_active=utc_now())
                )
                await session.commit()
        except Exception:
            logger.warning("Failed to refresh last active timestamp for sandbox %s", sandbox_id, exc_info=True)

    def _build_return_to(self, scope: Scope, host: str) -> str:
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("latin-1")
        scheme = _request_scheme(scope)
        base = f"{scheme}://{host}{path}"
        if query_string:
            return f"{base}?{query_string}"
        return base

    def _build_bootstrap_redirect(self, scope: Scope, host: str) -> str:
        return_to = self._build_return_to(scope, host)
        return f"{settings.app_base_url.rstrip('/')}/v1/browser/bootstrap?{urlencode({'return_to': return_to})}"

    @staticmethod
    def _set_sandbox_cookie(response: Response, sandbox_id: str, issued_via: str) -> None:
        response.set_cookie(
            key=SANDBOX_WEB_COOKIE_NAME,
            value=issue_sandbox_web_cookie(sandbox_id=sandbox_id, issued_via=issued_via),
            max_age=SANDBOX_WEB_COOKIE_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            secure=not settings.debug,
            path="/",
        )

    async def _exchange_open_credentials(self, request: Request, sandbox: Sandbox) -> Response:
        set_request_context(request, sandbox_id=sandbox.id)
        ticket = request.query_params.get("ticket")
        token = request.query_params.get("token")
        next_path = _sanitize_next_path(request.query_params.get("next"))

        if ticket:
            payload = verify_bootstrap_ticket(ticket)
            if payload is None or payload.get("sandbox_id") != sandbox.id:
                return Response("Invalid or expired bootstrap ticket.", status_code=401)
            next_path = _sanitize_next_path(str(payload.get("next_path", next_path)))
            await self._touch_last_active(sandbox.id)
            response = RedirectResponse(url=next_path, status_code=303)
            self._set_sandbox_cookie(response, sandbox.id, "bootstrap")
            return response

        if token:
            async with async_session() as session:
                result = await session.execute(
                    select(SandboxWebLink).where(
                        SandboxWebLink.sandbox_id == sandbox.id,
                        SandboxWebLink.id == token,
                        SandboxWebLink.gmt_deleted.is_(None),
                    )
                )
                link = result.scalar_one_or_none()
                if link is None or link.is_expired():
                    set_request_context(request, error_code="sandbox_web_link_invalid")
                    await record_audit_event(
                        session,
                        action="sandbox.web_link.open",
                        target_type="sandbox",
                        target_id=sandbox.id,
                        result="failure",
                        error_code="sandbox_web_link_invalid",
                        metadata={"issued_via": "open_link"},
                        request=request,
                    )
                    await session.commit()
                    return Response("Invalid or expired sandbox web link.", status_code=401)
                link.gmt_last_used = utc_now()
                link.gmt_updated = utc_now()
                sandbox.gmt_last_active = utc_now()
                session.add(link)
                session.add(sandbox)
                await record_audit_event(
                    session,
                    action="sandbox.web_link.open",
                    target_type="sandbox",
                    target_id=sandbox.id,
                    metadata={"issued_via": "open_link"},
                    request=request,
                )
                await session.commit()

            response = RedirectResponse(url=next_path, status_code=303)
            self._set_sandbox_cookie(response, sandbox.id, "open_link")
            return response

        return Response("Missing sandbox web credential.", status_code=400)

    async def _proxy_http(self, request: Request, scope: Scope, receive: Receive, send: Send, sandbox: Sandbox) -> None:
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
        target_url = build_sandbox_url(
            sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id,
            full_path,
        )
        logger.debug("Subdomain proxy %s %s → %s", request.method, sandbox.name, target_url)

        client = await get_http_client()
        outgoing = _strip_internal_auth(headers)

        try:
            req = client.build_request(method=request.method, url=target_url, headers=outgoing, content=body)
            resp = await client.send(req, stream=True)
        except Exception:
            logger.exception("Subdomain proxy failed for sandbox %s", sandbox.id)
            await _html_starting()(scope, receive, send)
            return

        resp_headers = _filter_response_headers(resp.headers)
        streaming = StreamingResponse(
            content=resp.aiter_bytes(),
            status_code=resp.status_code,
            headers=resp_headers,
        )
        await streaming(scope, receive, send)

    async def _handle_http(self, scope: Scope, receive: Receive, send: Send, sandbox_id: str, host: str) -> None:
        request = Request(scope, receive)
        sandbox = await self._load_sandbox(sandbox_id)
        if sandbox is None:
            await _html_not_found()(scope, receive, send)
            return

        if scope.get("path") == "/_treadstone/open":
            response = await self._exchange_open_credentials(request, sandbox)
            await response(scope, receive, send)
            return

        token = request.cookies.get(SANDBOX_WEB_COOKIE_NAME)
        payload = verify_sandbox_web_cookie(token) if token else None
        if payload is None or payload.get("sandbox_id") != sandbox.id:
            response = RedirectResponse(url=self._build_bootstrap_redirect(scope, host), status_code=303)
            await response(scope, receive, send)
            return

        if sandbox.status != SandboxStatus.READY.value:
            await _html_starting()(scope, receive, send)
            return

        await self._touch_last_active(sandbox.id)
        await self._proxy_http(request, scope, receive, send, sandbox)

    async def _handle_websocket(self, scope: Scope, receive: Receive, send: Send, sandbox_id: str) -> None:
        sandbox = await self._load_sandbox(sandbox_id)
        if sandbox is None or sandbox.status != SandboxStatus.READY.value:
            websocket = WebSocket(scope, receive, send)
            await websocket.close(code=1008)
            return

        websocket = WebSocket(scope, receive, send)
        token = websocket.cookies.get(SANDBOX_WEB_COOKIE_NAME)
        payload = verify_sandbox_web_cookie(token) if token else None
        if payload is None or payload.get("sandbox_id") != sandbox.id:
            await websocket.close(code=1008)
            return

        await self._touch_last_active(sandbox.id)

        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("latin-1")
        if query_string:
            path = f"{path}?{query_string}"
        logger.debug("Subdomain WS proxy %s → %s", sandbox.name, path)

        await websocket.accept()
        try:
            await proxy_websocket(
                client_ws=websocket,
                sandbox_id=sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id,
                path=path,
            )
        except Exception:
            try:
                await websocket.close(code=1011, reason="upstream connection failed")
            except RuntimeError:
                pass
