import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi_users.password import PasswordHelper
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from treadstone.api.deps import get_current_admin, get_current_control_plane_user
from treadstone.api.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyScope,
    ApiKeySummary,
    ChangePasswordRequest,
    CreateApiKeyRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    UpdateApiKeyRequest,
    UserDetailResponse,
    UserListResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError, ValidationError
from treadstone.core.users import COOKIE_MAX_AGE, cookie_transport, get_jwt_strategy
from treadstone.models.api_key import (
    ApiKey,
    ApiKeySandboxGrant,
    build_api_key_preview,
    hash_api_key_secret,
)
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import Invitation, Role, User, random_id, utc_now

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _default_api_key_scope() -> ApiKeyScope:
    return ApiKeyScope()


async def authenticate_email_password(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.unique().scalar_one_or_none()

    if user is None or not user.is_active:
        raise BadRequestError("Invalid email or password")

    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(password, user.hashed_password)
    if not valid:
        raise BadRequestError("Invalid email or password")

    return user


async def write_session_cookie(response: Response, user: User) -> str:
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    response.set_cookie(
        key="session",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=cookie_transport.cookie_secure,
    )
    return token


async def _validate_owned_sandbox_ids(session: AsyncSession, owner_id: str, sandbox_ids: list[str]) -> list[str]:
    if not sandbox_ids:
        return []

    deduped = list(dict.fromkeys(sandbox_ids))
    result = await session.execute(
        select(Sandbox.id).where(
            Sandbox.owner_id == owner_id,
            Sandbox.id.in_(deduped),
        )
    )
    owned_ids = result.scalars().all()
    if set(owned_ids) != set(deduped):
        raise ValidationError("sandbox_ids must all belong to the current user.")
    return deduped


async def _resolve_api_key_scope(
    session: AsyncSession,
    owner_id: str,
    scope: ApiKeyScope | None,
) -> tuple[ApiKeyScope, list[str]]:
    resolved_scope = scope or _default_api_key_scope()
    sandbox_ids = await _validate_owned_sandbox_ids(session, owner_id, resolved_scope.data_plane.sandbox_ids)
    return resolved_scope, sandbox_ids


def _serialize_api_key_scope(api_key: ApiKey) -> dict:
    sandbox_ids = [grant.sandbox_id for grant in api_key.sandbox_grants]
    return {
        "control_plane": api_key.control_plane_enabled,
        "data_plane": {"mode": api_key.data_plane_mode, "sandbox_ids": sandbox_ids},
    }


def _serialize_api_key_summary(api_key: ApiKey) -> dict:
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_preview,
        "created_at": api_key.gmt_created,
        "updated_at": api_key.gmt_updated,
        "expires_at": api_key.gmt_expires,
        "scope": _serialize_api_key_scope(api_key),
    }


async def _replace_api_key_sandbox_grants(session: AsyncSession, api_key: ApiKey, sandbox_ids: list[str]) -> None:
    await session.execute(delete(ApiKeySandboxGrant).where(ApiKeySandboxGrant.api_key_id == api_key.id))
    for sandbox_id in sandbox_ids:
        session.add(ApiKeySandboxGrant(api_key_id=api_key.id, sandbox_id=sandbox_id))


async def _load_api_key_with_grants(session: AsyncSession, key_id: str) -> ApiKey:
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.id == key_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with email + password, set session cookie."""
    user = await authenticate_email_password(session, str(body.email), body.password)

    response = Response(
        content='{"detail":"Login successful"}',
        media_type="application/json",
    )
    await write_session_cookie(response, user)
    return response


@router.post("/logout", response_model=MessageResponse)
async def logout():
    """Clear the session cookie."""
    response = Response(
        content='{"detail":"Logout successful"}',
        media_type="application/json",
    )
    response.delete_cookie(key="session")
    return response


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    count_result = await session.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar_one()
    is_first_user = user_count == 0

    invitation: Invitation | None = None
    if settings.register_mode == "invitation" and not is_first_user:
        if not body.invitation_token:
            raise ForbiddenError("Invitation token required")
        inv_result = await session.execute(select(Invitation).where(Invitation.token == body.invitation_token))
        invitation = inv_result.scalar_one_or_none()
        if not invitation or not invitation.is_valid():
            raise ForbiddenError("Invalid or expired invitation")
        if invitation.email != body.email:
            raise ForbiddenError("Invitation email mismatch")

    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.unique().scalar_one_or_none():
        raise ConflictError("Email already registered")

    ph = PasswordHelper()
    hashed = ph.hash(body.password)

    try:
        role = Role.ADMIN if is_first_user else (Role(invitation.role) if invitation else Role.RO)
    except ValueError as exc:
        raise ForbiddenError("Invalid invitation role") from exc
    user = User(
        email=body.email,
        hashed_password=hashed,
        is_active=True,
        is_superuser=(role == Role.ADMIN),
        is_verified=True,
        role=role.value,
    )
    session.add(user)

    if invitation:
        await invitation.use(session)
    else:
        await session.commit()

    await session.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/invite", status_code=status.HTTP_201_CREATED, response_model=InviteResponse)
async def invite(
    body: InviteRequest,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    token = secrets.token_urlsafe(32)
    inv = Invitation(
        email=body.email,
        token=token,
        created_by=current_user.email,
        expires_at=utc_now() + timedelta(days=7),
        role=body.role,
    )
    session.add(inv)
    await session.commit()
    return {"token": token, "email": body.email, "expires_at": inv.expires_at}


@router.get("/user", response_model=UserDetailResponse)
async def get_user(current_user: User = Depends(get_current_control_plane_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of items to return."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
):
    if current_user.role == Role.ADMIN.value:
        result = await session.execute(select(User))
        users = list(result.unique().scalars().all())
    else:
        users = [current_user]
    total = len(users)
    page = users[offset : offset + limit]
    return {"items": [{"id": u.id, "email": u.email, "role": u.role} for u in page], "total": total}


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(body.old_password, current_user.hashed_password)
    if not valid:
        raise BadRequestError("Wrong current password")
    user = await session.get(User, current_user.id)
    if not user:
        raise NotFoundError("User", current_user.id)
    user.hashed_password = ph.hash(body.new_password)
    session.add(user)
    await session.commit()
    return {"detail": "Password changed"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == current_user.id:
        raise BadRequestError("Cannot delete yourself")
    target = await session.get(User, user_id)
    if not target:
        raise NotFoundError("User", user_id)
    if target.role == Role.ADMIN.value:
        admin_count_result = await session.execute(
            select(func.count()).select_from(User).where(User.role == Role.ADMIN.value)
        )
        if admin_count_result.scalar_one() <= 1:
            raise BadRequestError("Cannot delete the last admin")
    await session.delete(target)
    await session.commit()


@router.post("/api-keys", status_code=status.HTTP_201_CREATED, response_model=ApiKeyResponse)
async def create_api_key(
    body: CreateApiKeyRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    key_value = "sk-" + secrets.token_hex(24)
    gmt_expires = None
    if body.expires_in is not None:
        gmt_expires = utc_now() + timedelta(seconds=body.expires_in)
    resolved_scope, sandbox_ids = await _resolve_api_key_scope(session, current_user.id, body.scope)
    api_key = ApiKey(
        id="key" + random_id(),
        key_hash=hash_api_key_secret(key_value),
        key_preview=build_api_key_preview(key_value),
        name=body.name,
        user_id=current_user.id,
        control_plane_enabled=resolved_scope.control_plane,
        data_plane_mode=resolved_scope.data_plane.mode.value,
        gmt_expires=gmt_expires,
    )
    session.add(api_key)
    await session.flush()
    await _replace_api_key_sandbox_grants(session, api_key, sandbox_ids)
    await session.commit()
    api_key = await _load_api_key_with_grants(session, api_key.id)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": key_value,
        "created_at": api_key.gmt_created,
        "updated_at": api_key.gmt_updated,
        "expires_at": api_key.gmt_expires,
        "scope": _serialize_api_key_scope(api_key),
    }


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    keys = result.scalars().all()
    return {"items": [_serialize_api_key_summary(k) for k in keys]}


@router.patch("/api-keys/{key_id}", response_model=ApiKeySummary)
async def update_api_key(
    key_id: str,
    body: UpdateApiKeyRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.id == key_id, ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key", key_id)

    if body.name is not None:
        api_key.name = body.name

    if body.expires_in is not None:
        api_key.gmt_expires = utc_now() + timedelta(seconds=body.expires_in)
    elif body.clear_expiration:
        api_key.gmt_expires = None

    if body.scope is not None:
        resolved_scope, sandbox_ids = await _resolve_api_key_scope(session, current_user.id, body.scope)
        api_key.control_plane_enabled = resolved_scope.control_plane
        api_key.data_plane_mode = resolved_scope.data_plane.mode.value
        await _replace_api_key_sandbox_grants(session, api_key, sandbox_ids)

    api_key.gmt_updated = utc_now()
    session.add(api_key)
    await session.commit()
    api_key = await _load_api_key_with_grants(session, api_key.id)
    return _serialize_api_key_summary(api_key)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key", key_id)
    api_key.gmt_deleted = utc_now()
    api_key.gmt_updated = utc_now()
    session.add(api_key)
    await session.commit()
