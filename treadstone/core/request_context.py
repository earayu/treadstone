from __future__ import annotations

import secrets
from typing import Any

from fastapi import Request
from starlette.datastructures import Headers
from starlette.types import Scope

REQUEST_ID_HEADER = "X-Request-Id"


def _ensure_state(scope: Scope) -> dict[str, Any]:
    state = scope.setdefault("state", {})
    if isinstance(state, dict):
        return state
    return getattr(state, "_state", vars(state))


def set_scope_context(scope: Scope, **values: Any) -> None:
    state = _ensure_state(scope)
    for key, value in values.items():
        if value is not None:
            state[key] = value


def set_request_context(request: Request, **values: Any) -> None:
    set_scope_context(request.scope, **values)


def get_scope_context(scope: Scope, key: str, default: Any = None) -> Any:
    return _ensure_state(scope).get(key, default)


def get_request_context(request: Request, key: str, default: Any = None) -> Any:
    return get_scope_context(request.scope, key, default)


def get_headers(scope: Scope) -> Headers:
    return Headers(scope=scope)


def get_client_ip(scope: Scope) -> str | None:
    headers = get_headers(scope)
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    client = scope.get("client")
    if client is None:
        return None
    host = client[0] if isinstance(client, tuple) else None
    return str(host) if host else None


def generate_request_id() -> str:
    return f"req_{secrets.token_hex(8)}"
