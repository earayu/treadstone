"""Platform domain errors — global caps, rate limits, waitlist."""

from treadstone.core.errors import TreadstoneError

__all__ = [
    "FeedbackRateLimitError",
    "UserRegistrationCapExceededError",
    "SandboxCapExceededError",
    "GlobalStorageCapExceededError",
    "WaitlistCapExceededError",
]


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
