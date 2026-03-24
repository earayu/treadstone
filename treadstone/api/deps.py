from __future__ import annotations

from typing import Literal

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from treadstone.core.database import get_session
from treadstone.core.errors import AuthInvalidError, AuthRequiredError, ForbiddenError
from treadstone.core.users import fastapi_users
from treadstone.models.api_key import ApiKey, ApiKeyDataPlaneMode, ApiKeySandboxGrant, hash_api_key_secret
from treadstone.models.user import Role, User

bearer_scheme = HTTPBearer(auto_error=False)
optional_cookie_user = fastapi_users.current_user(optional=True, active=True)


def _set_auth_context(
    request: Request,
    credential_type: Literal["cookie", "api_key"],
    api_key: ApiKey | None = None,
) -> None:
    request.state.credential_type = credential_type
    request.state.api_key_id = api_key.id if api_key is not None else None


async def _get_active_user(session: AsyncSession, user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
    return result.unique().scalar_one_or_none()


async def _authenticate_api_key_value(session: AsyncSession, secret: str) -> tuple[ApiKey, User] | None:
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(
            ApiKey.key_hash == hash_api_key_secret(secret),
            ApiKey.gmt_deleted.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None or api_key.is_expired():
        return None
    user = await _get_active_user(session, api_key.user_id)
    if user is None:
        return None
    return api_key, user


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

        auth_result = await _authenticate_api_key_value(session, credentials.credentials)
        if auth_result is None:
            raise AuthInvalidError("Invalid or expired API key.")
        api_key, user = auth_result
        if not api_key.control_plane_enabled:
            raise ForbiddenError("This API key does not have control plane access.")

        _set_auth_context(request, "api_key", api_key)
        return user

    if cookie_user is None:
        raise AuthRequiredError()

    _set_auth_context(request, "cookie")
    return cookie_user


async def get_current_data_plane_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
    cookie_user: User | None = Depends(optional_cookie_user),
) -> User:
    """Data plane auth accepts only API keys with data plane access."""
    if credentials is None:
        if cookie_user is not None:
            raise AuthInvalidError("API Key required for data plane access.")
        raise AuthRequiredError("API Key required.")

    if not credentials.credentials.startswith("sk-"):
        raise AuthInvalidError("API Key required for data plane access.")

    auth_result = await _authenticate_api_key_value(session, credentials.credentials)
    if auth_result is None:
        raise AuthInvalidError("Invalid or expired API key.")
    api_key, user = auth_result
    if api_key.data_plane_mode == ApiKeyDataPlaneMode.NONE.value:
        raise ForbiddenError("This API key does not have data plane access.")

    sandbox_id = request.path_params.get("sandbox_id")
    if sandbox_id and api_key.data_plane_mode == ApiKeyDataPlaneMode.SELECTED.value:
        result = await session.execute(
            select(ApiKeySandboxGrant.sandbox_id).where(
                ApiKeySandboxGrant.api_key_id == api_key.id,
                ApiKeySandboxGrant.sandbox_id == sandbox_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ForbiddenError("This API key does not have access to this sandbox.")

    _set_auth_context(request, "api_key", api_key)
    return user


async def get_current_admin(user: User = Depends(get_current_control_plane_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise ForbiddenError("Admin required")
    return user
