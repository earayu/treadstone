"""Test-support endpoints — only available when email_backend=memory AND debug=True."""

from __future__ import annotations

from fastapi import APIRouter, Query

from treadstone.config import settings
from treadstone.core.errors import NotFoundError
from treadstone.services.email import MemoryBackend, get_email_backend

router = APIRouter(prefix="/v1/test-support", tags=["test-support"])


def _guard() -> MemoryBackend:
    if settings.email_backend != "memory" or not settings.debug:
        raise NotFoundError("endpoint", "test-support")
    backend = get_email_backend()
    if not isinstance(backend, MemoryBackend):
        raise NotFoundError("endpoint", "test-support")
    return backend


@router.get("/emails/latest-verification", include_in_schema=False)
async def get_latest_verification_email(email: str = Query(...)):
    """Return the latest captured verification email for the given address."""
    backend = _guard()
    for entry in reversed(backend.sent):
        if entry.to == email:
            return {"to": entry.to, "token": entry.token, "verify_url": entry.verify_url}
    raise NotFoundError("verification email", email)
