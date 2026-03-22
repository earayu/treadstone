import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_admin, get_current_user
from treadstone.api.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ChangePasswordRequest,
    CreateApiKeyRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    UserDetailResponse,
    UserListResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from treadstone.core.users import COOKIE_MAX_AGE, get_jwt_strategy
from treadstone.models.api_key import ApiKey
from treadstone.models.user import Invitation, Role, User, random_id, utc_now

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with email + password, set session cookie."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.unique().scalar_one_or_none()

    if user is None or not user.is_active:
        raise BadRequestError("Invalid email or password")

    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(body.password, user.hashed_password)
    if not valid:
        raise BadRequestError("Invalid email or password")

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    response = Response(
        content='{"detail":"Login successful"}',
        media_type="application/json",
    )
    response.set_cookie(
        key="session",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
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

    role = Role.ADMIN if is_first_user else (Role(invitation.role) if invitation else Role.RO)
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
async def get_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    key_value = "sk-" + secrets.token_hex(24)
    gmt_expires = None
    if body.expires_in is not None:
        gmt_expires = utc_now() + timedelta(seconds=body.expires_in)
    api_key = ApiKey(
        id="key" + random_id(),
        key=key_value,
        name=body.name,
        user_id=current_user.id,
        gmt_expires=gmt_expires,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": api_key.key,
        "created_at": api_key.gmt_created,
        "expires_at": api_key.gmt_expires,
    }


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    keys = result.scalars().all()
    return {
        "items": [
            {
                "id": k.id,
                "name": k.name,
                "key_prefix": k.key[:7] + "..." + k.key[-4:],
                "created_at": k.gmt_created,
                "expires_at": k.gmt_expires,
            }
            for k in keys
        ]
    }


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key", key_id)
    api_key.gmt_deleted = utc_now()
    session.add(api_key)
    await session.commit()
