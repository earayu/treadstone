"""Metering domain errors — quotas, limits, billing enforcement."""

from treadstone.core.errors import TreadstoneError

__all__ = [
    "ComputeQuotaExceededError",
    "StorageQuotaExceededError",
    "ConcurrentLimitError",
    "TemplateNotAllowedError",
    "SandboxDurationExceededError",
]


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
