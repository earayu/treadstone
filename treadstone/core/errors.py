"""Unified error format for Treadstone API.

All errors return:
    {"error": {"code": "...", "message": "...", "status": 404}}
"""


class TreadstoneError(Exception):
    """Base exception for all Treadstone API errors."""

    def __init__(self, code: str, message: str, status: int = 500):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message, "status": self.status}}


class AuthRequiredError(TreadstoneError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(code="auth_required", message=message, status=401)


class AuthInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired credentials"):
        super().__init__(code="auth_invalid", message=message, status=401)


class ForbiddenError(TreadstoneError):
    def __init__(self, message: str = "You don't have access to this resource"):
        super().__init__(code="forbidden", message=message, status=403)


class SandboxNotFoundError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_not_found",
            message=f"Sandbox {sandbox_id} does not exist or you don't have access to it.",
            status=404,
        )


class TemplateNotFoundError(TreadstoneError):
    def __init__(self, template_name: str):
        super().__init__(
            code="template_not_found",
            message=f"Template '{template_name}' not found.",
            status=404,
        )


class SandboxNotReadyError(TreadstoneError):
    def __init__(self, sandbox_id: str, current_status: str):
        super().__init__(
            code="sandbox_not_ready",
            message=f"Sandbox {sandbox_id} is {current_status}, not ready for this operation.",
            status=409,
        )


class SandboxUnreachableError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_unreachable",
            message=f"Could not connect to sandbox {sandbox_id}.",
            status=502,
        )


class SandboxTimeoutError(TreadstoneError):
    def __init__(self, sandbox_id: str):
        super().__init__(
            code="sandbox_timeout",
            message=f"Sandbox {sandbox_id} did not respond in time.",
            status=504,
        )


class StorageBackendNotReadyError(TreadstoneError):
    def __init__(self, storage_class_name: str):
        super().__init__(
            code="storage_backend_not_ready",
            message=(
                "Persistent sandbox storage is not ready. "
                f"StorageClass '{storage_class_name}' was not found in the cluster."
            ),
            status=503,
        )


class SandboxNameConflictError(TreadstoneError):
    def __init__(self, name: str):
        super().__init__(
            code="sandbox_name_conflict",
            message=f"A sandbox named '{name}' already exists for the current user.",
            status=409,
        )


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


class InvalidTransitionError(TreadstoneError):
    def __init__(self, sandbox_id: str, from_status: str, to_status: str):
        super().__init__(
            code="invalid_transition",
            message=f"Cannot transition sandbox {sandbox_id} from {from_status} to {to_status}.",
            status=409,
        )


# ── Metering Errors ──


class ComputeQuotaExceededError(TreadstoneError):
    def __init__(self, monthly_used: float, monthly_limit: float, extra_remaining: float):
        super().__init__(
            code="compute_quota_exceeded",
            message=(
                f"Compute credits exhausted. "
                f"Monthly used: {monthly_used:.1f} / {monthly_limit:.1f} vCPU-hours, "
                f"extra remaining: {extra_remaining:.1f} vCPU-hours. "
                f"Please wait for the next billing cycle or purchase additional credits."
            ),
            status=402,
        )


class StorageQuotaExceededError(TreadstoneError):
    def __init__(self, current_used_gib: int, requested_gib: int, total_quota_gib: int):
        super().__init__(
            code="storage_quota_exceeded",
            message=(
                f"Storage quota exceeded. "
                f"Current used: {current_used_gib} GiB, requested: {requested_gib} GiB, "
                f"total quota: {total_quota_gib} GiB "
                f"(available: {total_quota_gib - current_used_gib} GiB). "
                f"Delete existing persistent sandboxes to free space, or upgrade your plan."
            ),
            status=402,
        )


class ConcurrentLimitError(TreadstoneError):
    def __init__(self, current_running: int, max_concurrent: int):
        super().__init__(
            code="concurrent_limit_exceeded",
            message=(
                f"Concurrent sandbox limit reached. "
                f"Running: {current_running} / {max_concurrent}. "
                f"Stop an existing sandbox before creating a new one."
            ),
            status=429,
        )


class TemplateNotAllowedError(TreadstoneError):
    def __init__(self, tier: str, template: str, allowed_templates: list[str]):
        super().__init__(
            code="template_not_allowed",
            message=(
                f"Template '{template}' is not available on the '{tier}' tier. "
                f"Allowed templates: {', '.join(allowed_templates)}. "
                f"Upgrade your plan to access this template."
            ),
            status=403,
        )


class SandboxDurationExceededError(TreadstoneError):
    def __init__(self, tier: str, max_duration_seconds: int):
        hours = max_duration_seconds // 3600
        minutes = (max_duration_seconds % 3600) // 60
        duration_str = f"{hours}h{minutes}m" if minutes else f"{hours}h"
        super().__init__(
            code="sandbox_duration_exceeded",
            message=(
                f"Requested sandbox duration exceeds the '{tier}' tier maximum of {duration_str}. "
                f"Reduce auto_stop_interval or upgrade your plan."
            ),
            status=400,
        )
