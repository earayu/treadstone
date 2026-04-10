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


class StorageSnapshotBackendNotReadyError(TreadstoneError):
    def __init__(self, snapshot_class_name: str):
        super().__init__(
            code="storage_snapshot_backend_not_ready",
            message=(
                "Cold snapshot storage is not ready. "
                f"VolumeSnapshotClass '{snapshot_class_name}' was not found in the cluster."
            ),
            status=503,
        )


class SandboxTemplateCatalogUnavailableError(TreadstoneError):
    def __init__(self, message: str = "Sandbox template catalog is temporarily unavailable."):
        super().__init__(
            code="sandbox_template_catalog_unavailable",
            message=message,
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


# ── Email Verification Errors ──


class EmailVerificationRequiredError(TreadstoneError):
    def __init__(self, message: str = "Email verification required before creating sandboxes."):
        super().__init__(code="email_verification_required", message=message, status=403)


class EmailVerificationTokenInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired verification token."):
        super().__init__(code="email_verification_token_invalid", message=message, status=400)


class EmailAlreadyVerifiedError(TreadstoneError):
    def __init__(self, message: str = "Email is already verified."):
        super().__init__(code="email_already_verified", message=message, status=400)


# ── Password Reset Errors ──


class PasswordResetTokenInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired password reset token."):
        super().__init__(code="password_reset_token_invalid", message=message, status=400)


class PasswordResetRateLimitedError(TreadstoneError):
    def __init__(self, message: str):
        super().__init__(code="password_reset_rate_limited", message=message, status=429)


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


class FeedbackRateLimitError(TreadstoneError):
    def __init__(self, wait_seconds: int):
        super().__init__(
            code="feedback_rate_limited",
            message=f"Please wait {wait_seconds} seconds before sending more feedback.",
            status=429,
        )


class UserRegistrationCapExceededError(TreadstoneError):
    def __init__(self, current_registered_users: int, max_registered_users: int):
        super().__init__(
            code="user_registration_cap_exceeded",
            message=(
                "User registration is temporarily unavailable. "
                f"Registered users: {current_registered_users} / {max_registered_users}."
            ),
            status=503,
        )


class SandboxCapExceededError(TreadstoneError):
    def __init__(self, current_sandboxes: int, max_total_sandboxes: int):
        super().__init__(
            code="sandbox_cap_exceeded",
            message=(
                "Sandbox creation is temporarily unavailable. "
                f"Total sandboxes: {current_sandboxes} / {max_total_sandboxes}."
            ),
            status=503,
        )


class GlobalStorageCapExceededError(TreadstoneError):
    def __init__(self, current_storage_gib: int, requested_storage_gib: int, max_total_storage_gib: int):
        super().__init__(
            code="global_storage_cap_exceeded",
            message=(
                "Persistent sandbox creation is temporarily unavailable. "
                f"Allocated storage: {current_storage_gib} GiB, requested: {requested_storage_gib} GiB, "
                f"limit: {max_total_storage_gib} GiB."
            ),
            status=503,
        )


class WaitlistCapExceededError(TreadstoneError):
    def __init__(self, current_waitlist_applications: int, max_waitlist_applications: int):
        super().__init__(
            code="waitlist_cap_exceeded",
            message=(
                "Waitlist submissions are temporarily unavailable. "
                f"Applications: {current_waitlist_applications} / {max_waitlist_applications}."
            ),
            status=503,
        )


class TemplateNotAllowedError(TreadstoneError):
    def __init__(self, tier: str, template: str, allowed_templates: list[str]):
        allowed_str = ", ".join(allowed_templates) if allowed_templates else "none"
        super().__init__(
            code="template_not_allowed",
            message=(
                f"Template '{template}' is not available on the '{tier}' tier. "
                f"Allowed templates: {allowed_str}. "
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
