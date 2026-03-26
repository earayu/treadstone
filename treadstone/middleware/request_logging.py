from __future__ import annotations

import json
import logging
import sys
import time
from datetime import UTC, datetime

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from treadstone.config import settings
from treadstone.core.request_context import (
    REQUEST_ID_HEADER,
    generate_request_id,
    get_client_ip,
    get_headers,
    get_scope_context,
    set_scope_context,
)

request_logger = logging.getLogger("treadstone.request")
if not request_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    request_logger.addHandler(handler)
request_logger.setLevel(logging.INFO)
request_logger.propagate = False


def _extract_sandbox_id(host: str | None) -> str | None:
    if not host or not settings.sandbox_domain:
        return None

    host_no_port = host.split(":")[0].lower()
    domain = settings.sandbox_domain.lower()
    if not host_no_port.endswith(f".{domain}"):
        return None

    subdomain = host_no_port[: -(len(domain) + 1)]
    prefix = settings.sandbox_subdomain_prefix
    if not subdomain.startswith(prefix):
        return None

    sandbox_id = subdomain[len(prefix) :]
    return sandbox_id or None


def _infer_route_kind(scope: Scope) -> str:
    host = get_headers(scope).get("host")
    sandbox_id = _extract_sandbox_id(host)
    if sandbox_id is None:
        return "api"
    return "subdomain_ws" if scope["type"] == "websocket" else "subdomain_http"


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        headers = get_headers(scope)
        request_id = headers.get(REQUEST_ID_HEADER) or generate_request_id()
        set_scope_context(scope, request_id=request_id, route_kind=_infer_route_kind(scope))

        response_code: int | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal response_code

            if message["type"] == "http.response.start":
                response_code = message["status"]
                response_headers = MutableHeaders(raw=message["headers"])
                response_headers[REQUEST_ID_HEADER] = request_id
            elif message["type"] == "websocket.http.response.start":
                response_code = message["status"]
                response_headers = MutableHeaders(raw=message["headers"])
                response_headers[REQUEST_ID_HEADER] = request_id
            elif message["type"] == "websocket.accept":
                response_code = 101
            elif message["type"] == "websocket.close" and response_code is None:
                response_code = int(message.get("code", 1000))

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            payload = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "INFO",
                "event": "http_request",
                "request_id": request_id,
                "method": scope.get("method", scope["type"].upper()),
                "path": scope.get("path"),
                "host": headers.get("host"),
                "status_code": response_code or 500,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "client_ip": get_client_ip(scope),
                "user_agent": headers.get("user-agent"),
                "actor_user_id": get_scope_context(scope, "actor_user_id"),
                "actor_api_key_id": get_scope_context(scope, "actor_api_key_id"),
                "credential_type": get_scope_context(scope, "credential_type"),
                "sandbox_id": get_scope_context(scope, "sandbox_id") or _extract_sandbox_id(headers.get("host")),
                "route_kind": get_scope_context(scope, "route_kind"),
                "error_code": get_scope_context(scope, "error_code"),
            }
            request_logger.info(json.dumps(payload, separators=(",", ":")))
