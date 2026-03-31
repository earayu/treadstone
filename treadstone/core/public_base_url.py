"""Resolve the externally visible control-plane base URL for API responses."""

from __future__ import annotations

from starlette.requests import Request


def public_control_plane_base_url(request: Request) -> str:
    """Return the base URL clients should use for control-plane links, with trailing slash.

    When TLS terminates at a load balancer or ingress, the ASGI scope often still
    reports ``http`` while ``X-Forwarded-Proto`` is ``https``. Use forwarded
    headers when present so ``urls.proxy`` and ``urls.web`` match what browsers
    and CLIs should call (HTTPS in production).

    If forwarded metadata is missing, falls back to :attr:`Request.base_url`
    (e.g. direct ``uvicorn`` to ``http://localhost:8000/`` in development).
    """
    headers = request.headers

    def _first(name: str) -> str:
        raw = headers.get(name)
        if not raw:
            return ""
        return raw.split(",")[0].strip()

    proto = _first("x-forwarded-proto").lower()
    host = _first("x-forwarded-host") or _first("host")

    if proto in ("http", "https") and host:
        return f"{proto}://{host}/"

    return str(request.base_url)
