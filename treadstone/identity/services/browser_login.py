from __future__ import annotations

from urllib.parse import urlparse

from treadstone.config import settings
from treadstone.core.errors import ValidationError


def extract_sandbox_id_from_return_host(host: str) -> str | None:
    if not settings.sandbox_domain:
        return None

    host_no_port = host.split(":")[0].lower()
    domain = settings.sandbox_domain.lower()

    if not host_no_port.endswith(f".{domain}"):
        return None

    subdomain = host_no_port[: -(len(domain) + 1)]
    if not subdomain or "." in subdomain:
        return None
    if not subdomain.startswith(settings.sandbox_subdomain_prefix):
        return None
    name = subdomain[len(settings.sandbox_subdomain_prefix) :]
    return name if name else None


def validate_browser_return_to(return_to: str) -> tuple[str, str, str, str]:
    parsed = urlparse(return_to)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("return_to must be an absolute sandbox Web UI URL.")

    sandbox_id = extract_sandbox_id_from_return_host(parsed.netloc)
    if sandbox_id is None:
        raise ValidationError("return_to must target a sandbox subdomain.")

    next_path = parsed.path or "/"
    if parsed.query:
        next_path = f"{next_path}?{parsed.query}"
    if parsed.fragment:
        next_path = f"{next_path}#{parsed.fragment}"

    return parsed.scheme, parsed.netloc, sandbox_id, next_path
