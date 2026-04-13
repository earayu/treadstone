"""Identity domain errors — authentication, authorization, email verification, password reset."""

from treadstone.core.errors import TreadstoneError

__all__ = [
    "AuthRequiredError",
    "AuthInvalidError",
    "ForbiddenError",
    "EmailVerificationRequiredError",
    "EmailVerificationTokenInvalidError",
    "EmailAlreadyVerifiedError",
    "PasswordResetTokenInvalidError",
    "PasswordResetRateLimitedError",
]


class AuthRequiredError(TreadstoneError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(code="auth_required", message=message, status=401)


class AuthInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired credentials"):
        super().__init__(code="auth_invalid", message=message, status=401)


class ForbiddenError(TreadstoneError):
    def __init__(self, message: str = "You don't have access to this resource"):
        super().__init__(code="forbidden", message=message, status=403)


class EmailVerificationRequiredError(TreadstoneError):
    def __init__(self, message: str = "Email verification required before creating sandboxes."):
        super().__init__(code="email_verification_required", message=message, status=403)


class EmailVerificationTokenInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired verification token."):
        super().__init__(code="email_verification_token_invalid", message=message, status=400)


class EmailAlreadyVerifiedError(TreadstoneError):
    def __init__(self, message: str = "Email is already verified."):
        super().__init__(code="email_already_verified", message=message, status=400)


class PasswordResetTokenInvalidError(TreadstoneError):
    def __init__(self, message: str = "Invalid or expired password reset token."):
        super().__init__(code="password_reset_token_invalid", message=message, status=400)


class PasswordResetRateLimitedError(TreadstoneError):
    def __init__(self, message: str):
        super().__init__(code="password_reset_rate_limited", message=message, status=429)
