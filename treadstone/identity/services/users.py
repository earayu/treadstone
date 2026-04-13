from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx_oauth.clients.github import GitHubOAuth2
from httpx_oauth.clients.google import GoogleOAuth2
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.identity.models.email_verification_log import EmailVerificationLog
from treadstone.identity.models.user import OAuthAccount, Role, User
from treadstone.identity.services.email import get_email_backend

__all__ = [
    "COOKIE_MAX_AGE",
    "UserManager",
    "auth_backend",
    "cookie_transport",
    "fastapi_users",
    "get_github_oauth_client",
    "get_google_oauth_client",
    "get_jwt_strategy",
    "get_user_db",
    "get_user_manager",
    "should_use_secure_cookies",
]

COOKIE_MAX_AGE = settings.session_ttl_seconds


def should_use_secure_cookies() -> bool:
    return not settings.debug and urlparse(settings.app_base_url).scheme == "https"


def get_google_oauth_client() -> GoogleOAuth2 | None:
    if settings.google_oauth_client_id and settings.google_oauth_client_secret:
        return GoogleOAuth2(
            settings.google_oauth_client_id,
            settings.google_oauth_client_secret,
        )
    return None


def get_github_oauth_client() -> GitHubOAuth2 | None:
    if settings.github_oauth_client_id and settings.github_oauth_client_secret:
        return GitHubOAuth2(
            settings.github_oauth_client_id,
            settings.github_oauth_client_secret,
        )
    return None


# ── UserManager ──
class UserManager(BaseUserManager[User, str]):
    reset_password_token_secret = settings.jwt_secret
    reset_password_token_lifetime_seconds = settings.reset_password_token_lifetime_seconds
    verification_token_secret = settings.jwt_secret
    verification_token_lifetime_seconds = settings.verification_token_lifetime_seconds

    def parse_id(self, value: str) -> str:
        return value

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """First registered user automatically becomes ADMIN."""
        session = self.user_db.session
        result = await session.execute(select(func.count()).select_from(User))
        count = result.scalar_one()
        if count == 1:
            user.role = Role.ADMIN.value
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None) -> None:
        reset_url = f"{settings.app_base_url.rstrip('/')}/auth/reset-password?token={token}"
        backend = get_email_backend()
        await backend.send_password_reset_email(to=user.email, token=token, reset_url=reset_url)

    async def on_after_request_verify(self, user: User, token: str, request: Request | None = None) -> None:
        verify_url = f"{settings.app_base_url.rstrip('/')}/auth/verify-email?token={token}"

        # fastapi-users request_verify() does not stage any DB writes before calling
        # this hook, so committing here is safe. If upgrading fastapi-users, verify this.
        session = self.user_db.session
        log_entry = EmailVerificationLog(user_id=user.id, email=user.email, token=token, verify_url=verify_url)
        session.add(log_entry)

        backend = get_email_backend()
        try:
            await backend.send_verification_email(to=user.email, token=token, verify_url=verify_url)
        except Exception:
            await session.rollback()
            raise

        await session.commit()


# ── FastAPI-Users DB dependency ──
async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, str], None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, str] = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


# ── Transport + Strategy + Backend ──
cookie_transport = CookieTransport(
    cookie_name="session",
    cookie_max_age=COOKIE_MAX_AGE,
    cookie_httponly=True,
    cookie_samesite="lax",
    cookie_secure=should_use_secure_cookies(),
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=COOKIE_MAX_AGE)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, str](get_user_manager, [auth_backend])
