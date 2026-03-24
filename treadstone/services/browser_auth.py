from __future__ import annotations

from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import jwt

from treadstone.config import settings
from treadstone.models.user import random_id, utc_now

BOOTSTRAP_TICKET_TTL_SECONDS = 300
OPEN_LINK_TTL_SECONDS = 7 * 24 * 60 * 60
SANDBOX_WEB_COOKIE_NAME = "ts_bui"
SANDBOX_WEB_COOKIE_TTL_SECONDS = 30 * 24 * 60 * 60
_JWT_ALGORITHM = "HS256"


def build_open_link_token() -> str:
    return "swl" + random_id(24)


def build_open_link_url(web_url: str, token: str) -> str:
    return f"{web_url.rstrip('/')}/_treadstone/open?{urlencode({'token': token})}"


def issue_bootstrap_ticket(*, sandbox_id: str, next_path: str) -> str:
    payload = {
        "kind": "bootstrap",
        "sandbox_id": sandbox_id,
        "next_path": next_path,
        "exp": utc_now() + timedelta(seconds=BOOTSTRAP_TICKET_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def verify_bootstrap_ticket(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("kind") != "bootstrap":
        return None
    return payload


def issue_sandbox_web_cookie(*, sandbox_id: str, issued_via: str) -> str:
    payload = {
        "kind": "sandbox_web",
        "sandbox_id": sandbox_id,
        "issued_via": issued_via,
        "exp": utc_now() + timedelta(seconds=SANDBOX_WEB_COOKIE_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def verify_sandbox_web_cookie(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("kind") != "sandbox_web":
        return None
    return payload
