"""Resolve the externally visible control-plane base URL for API responses."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.requests import Request

from treadstone.config import is_local_hostname, settings


def _configured_public_base_url() -> str | None:
    """Return the configured public app origin when it is a non-local deployment URL."""
    parsed = urlparse(settings.app_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or is_local_hostname(parsed.hostname):
        return None
    return f"{settings.app_base_url.rstrip('/')}/"


def public_control_plane_base_url(request: Request) -> str:
    """Return the base URL clients should use for control-plane links, with trailing slash.

    Public deployments should not derive user-visible origins from request
    headers, because ``Host`` / ``X-Forwarded-*`` can be spoofed before a trusted
    proxy normalizes them. When ``TREADSTONE_APP_BASE_URL`` is configured to a
    non-local origin, treat that as the canonical public base URL.

    Local development still falls back to forwarded metadata and request base URL
    so port-forward, ingress, and direct ``uvicorn`` access keep working.
    """
    configured = _configured_public_base_url()
    if configured is not None:
        return configured

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
