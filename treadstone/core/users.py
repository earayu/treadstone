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
from treadstone.models.user import OAuthAccount, Role, User

COOKIE_MAX_AGE = 86400  # 24 hours


def should_use_secure_cookies() -> bool:
    return not settings.debug and urlparse(settings.api_base_url).scheme == "https"


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
    verification_token_secret = settings.jwt_secret

    def parse_id(self, value: str) -> str:
        return value

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """First registered user automatically becomes ADMIN."""
        session = self.user_db.session
        result = await session.execute(select(func.count()).select_from(User))
        count = result.scalar_one()
        if count == 1:
            user.role = Role.ADMIN.value
            user.is_superuser = True
            session.add(user)
            await session.commit()
            await session.refresh(user)

    async def on_after_forgot_password(self, user: User, token: str, request: Request | None = None) -> None:
        pass  # TODO: send email

    async def on_after_request_verify(self, user: User, token: str, request: Request | None = None) -> None:
        pass  # TODO: send email


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
