from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from treadstone.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VerificationEmail:
    to: str
    token: str
    verify_url: str


@dataclass
class PasswordResetEmail:
    to: str
    token: str
    reset_url: str


class EmailBackend(Protocol):
    async def send_verification_email(self, to: str, token: str, verify_url: str) -> None: ...
    async def send_password_reset_email(self, to: str, token: str, reset_url: str) -> None: ...


class MemoryBackend:
    def __init__(self) -> None:
        self.sent: list[VerificationEmail] = []
        self.password_reset_emails: list[PasswordResetEmail] = []

    async def send_verification_email(self, to: str, token: str, verify_url: str) -> None:
        email = VerificationEmail(to=to, token=token, verify_url=verify_url)
        self.sent.append(email)
        logger.info("MemoryBackend captured verification email to=%s url=%s", to, verify_url)

    async def send_password_reset_email(self, to: str, token: str, reset_url: str) -> None:
        email = PasswordResetEmail(to=to, token=token, reset_url=reset_url)
        self.password_reset_emails.append(email)
        logger.info("MemoryBackend captured password reset email to=%s url=%s", to, reset_url)


class ResendBackend:
    def __init__(self) -> None:
        import resend

        resend.api_key = settings.resend_api_key
        self._resend = resend

    async def send_verification_email(self, to: str, token: str, verify_url: str) -> None:
        import asyncio

        await asyncio.to_thread(
            self._resend.Emails.send,
            {
                "from": settings.email_from,
                "to": [to],
                "subject": "Verify your Treadstone email",
                "html": (
                    f"<p>Click the link below to verify your email address:</p>"
                    f'<p><a href="{verify_url}">{verify_url}</a></p>'
                    f"<p>This link will expire in {settings.verification_token_lifetime_seconds // 60} minutes.</p>"
                ),
            },
        )
        logger.info("Resend verification email sent to=%s", to)

    async def send_password_reset_email(self, to: str, token: str, reset_url: str) -> None:
        import asyncio

        await asyncio.to_thread(
            self._resend.Emails.send,
            {
                "from": settings.email_from,
                "to": [to],
                "subject": "Reset your Treadstone password",
                "html": (
                    f"<p>Click the link below to reset your Treadstone password:</p>"
                    f'<p><a href="{reset_url}">{reset_url}</a></p>'
                    f"<p>This link will expire in {settings.reset_password_token_lifetime_seconds // 60} minutes.</p>"
                ),
            },
        )
        logger.info("Resend password reset email sent to=%s", to)


_backend: EmailBackend | None = None


def get_email_backend() -> EmailBackend:
    global _backend
    if _backend is not None:
        return _backend

    if settings.email_backend == "resend":
        _backend = ResendBackend()
    else:
        _backend = MemoryBackend()
    return _backend


def reset_email_backend() -> None:
    """Reset the cached singleton (used by tests)."""
    global _backend
    _backend = None
