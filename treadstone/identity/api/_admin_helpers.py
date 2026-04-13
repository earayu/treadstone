"""Shared admin helper functions used across admin sub-routers."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.audit.services.audit import record_audit_event
from treadstone.core.errors import NotFoundError
from treadstone.identity.models.user import User


async def _record_sensitive_admin_read(
    session: AsyncSession,
    *,
    request: Request,
    action: str,
    target_type: str,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    await record_audit_event(
        session,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata,
        request=request,
    )


async def _require_user(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.unique().scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    return user


async def _load_existing_user_ids(session: AsyncSession, user_ids: list[str]) -> set[str]:
    """Resolve batch user existence with a single query."""
    unique_user_ids = {user_id for user_id in user_ids}
    if not unique_user_ids:
        return set()

    result = await session.execute(select(User.id).where(User.id.in_(unique_user_ids)))
    return set(result.scalars().all())
