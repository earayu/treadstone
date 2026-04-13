"""Unified error format for Treadstone API.

All errors return:
    {"error": {"code": "...", "message": "...", "status": 404}}

Base class and generic (non-domain) errors live here.  Domain-specific
errors are defined in their respective modules and re-exported below for
backward compatibility.
"""


# ── Base class ─────────────────────────────────────────────────────────────


class TreadstoneError(Exception):
    """Base exception for all Treadstone API errors."""

    def __init__(self, code: str, message: str, status: int = 500):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "status": self.status}}


# ── Generic (non-domain) errors ───────────────────────────────────────────


class NotFoundError(TreadstoneError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code="not_found",
            message=f"{resource} '{identifier}' not found.",
            status=404,
        )


class ConflictError(TreadstoneError):
    def __init__(self, message: str):
        super().__init__(code="conflict", message=message, status=409)


class BadRequestError(TreadstoneError):
    def __init__(self, message: str):
        super().__init__(code="bad_request", message=message, status=400)


class ValidationError(TreadstoneError):
    def __init__(self, message: str = "Request validation failed"):
        super().__init__(code="validation_error", message=message, status=422)


# ── Domain error re-exports (backward compatibility) ──────────────────────
# All existing ``from treadstone.core.errors import XError`` statements
# continue to work.  New code should import from the owning module instead.

from treadstone.identity.errors import *  # noqa: E402,F401,F403
from treadstone.metering.errors import *  # noqa: E402,F401,F403
from treadstone.platform.errors import *  # noqa: E402,F401,F403
from treadstone.sandbox.errors import *  # noqa: E402,F401,F403
from treadstone.storage.errors import *  # noqa: E402,F401,F403
