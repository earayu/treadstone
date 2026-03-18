import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_admin, get_current_user
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.users import auth_backend, fastapi_users
from treadstone.models.user import Invitation, Role, User, utc_now

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── fastapi-users built-in login / logout ──
router.include_router(fastapi_users.get_auth_router(auth_backend))


# ── Register ──
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    invitation_token: str | None = None


@router.post("/register", status_code=status.HTTP_201_CREATED)
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
            raise HTTPException(status_code=403, detail="Invitation token required")
        inv_result = await session.execute(select(Invitation).where(Invitation.token == body.invitation_token))
        invitation = inv_result.scalar_one_or_none()
        if not invitation or not invitation.is_valid():
            raise HTTPException(status_code=403, detail="Invalid or expired invitation")
        if invitation.email != body.email:
            raise HTTPException(status_code=403, detail="Invitation email mismatch")

    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.unique().scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    from fastapi_users.password import PasswordHelper

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


# ── Invite ──
class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Role.RO.value


@router.post("/invite", status_code=status.HTTP_201_CREATED)
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
    return {"token": token, "email": body.email, "expires_at": str(inv.expires_at)}


# ── Current user info ──
@router.get("/user")
async def get_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# ── List users ──
@router.get("/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if current_user.role == Role.ADMIN.value:
        result = await session.execute(select(User))
        users = result.unique().scalars().all()
    else:
        users = [current_user]
    return [{"id": u.id, "email": u.email, "role": u.role} for u in users]


# ── Change password ──
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from fastapi_users.password import PasswordHelper

    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(body.old_password, current_user.hashed_password)
    if not valid:
        raise HTTPException(status_code=400, detail="Wrong current password")
    current_user.hashed_password = ph.hash(body.new_password)
    session.add(current_user)
    await session.commit()
    return {"detail": "Password changed"}


# ── Delete user ──
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.role == Role.ADMIN.value:
        admin_count_result = await session.execute(
            select(func.count()).select_from(User).where(User.role == Role.ADMIN.value)
        )
        if admin_count_result.scalar_one() <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")
    await session.delete(target)
    await session.commit()
