from __future__ import annotations

from typing import Literal, TypedDict

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.core.database import get_session
from treadstone.core.errors import AuthInvalidError, AuthRequiredError, ForbiddenError
from treadstone.core.users import fastapi_users
from treadstone.models.api_key import ApiKey, hash_api_key_secret
from treadstone.models.user import Role, User
from treadstone.services.sandbox_token import verify_sandbox_token


class SandboxTokenPayload(TypedDict):
    sandbox_id: str
    user_id: str


bearer_scheme = HTTPBearer(auto_error=False)
optional_cookie_user = fastapi_users.current_user(optional=True, active=True)


def _set_auth_context(
    request: Request,
    credential_type: Literal["cookie", "api_key", "sandbox_token"],
    sandbox_token_payload: SandboxTokenPayload | None = None,
) -> None:
    request.state.credential_type = credential_type
    request.state.sandbox_token_payload = sandbox_token_payload


async def _get_active_user(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.unique().scalar_one_or_none()


async def _authenticate_api_key_value(session: AsyncSession, secret: str) -> User | None:
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == hash_api_key_secret(secret),
            ApiKey.gmt_deleted.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None or api_key.is_expired():
        return None
    return await _get_active_user(session, api_key.user_id)


async def get_current_control_plane_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
    cookie_user: User | None = Depends(optional_cookie_user),
) -> User:
    """Control plane auth accepts API keys or session cookies."""
    if credentials:
        if not credentials.credentials.startswith("sk-"):
            raise AuthInvalidError("Control plane endpoints accept API keys or session cookies.")

        user = await _authenticate_api_key_value(session, credentials.credentials)
        if user is None:
            raise AuthInvalidError("Invalid or expired API key.")

        _set_auth_context(request, "api_key")
        return user

    if cookie_user is None:
        raise AuthRequiredError()

    _set_auth_context(request, "cookie")
    return cookie_user


async def get_current_sandbox_token_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
    cookie_user: User | None = Depends(optional_cookie_user),
) -> User:
    """Data plane auth accepts only sandbox-scoped JWTs."""
    if credentials is None:
        if cookie_user is not None:
            raise AuthInvalidError("Sandbox Token required for data plane access.")
        raise AuthRequiredError("Sandbox Token required.")

    if credentials.credentials.startswith("sk-"):
        raise AuthInvalidError("Sandbox Token required for data plane access.")

    try:
        payload = verify_sandbox_token(credentials.credentials)
    except jwt.InvalidTokenError as exc:
        raise AuthInvalidError("Invalid or expired Sandbox Token.") from exc

    user = await _get_active_user(session, payload["user_id"])
    if user is None:
        raise AuthInvalidError("Invalid or expired Sandbox Token.")

    _set_auth_context(request, "sandbox_token", payload)
    return user


async def get_current_admin(user: User = Depends(get_current_control_plane_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise ForbiddenError("Admin required")
    return user
