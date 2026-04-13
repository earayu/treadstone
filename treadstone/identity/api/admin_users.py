"""Admin API — user lookup, usage, and email verification endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.schemas import (
    ResolveEmailsRequest,
    ResolveEmailsResponse,
    UsageSummaryResponse,
    UserLookupResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import NotFoundError
from treadstone.identity.api.deps import get_current_admin, get_current_admin_session
from treadstone.identity.models.email_verification_log import EmailVerificationLog
from treadstone.identity.models.user import User
from treadstone.metering.services.metering_service import MeteringService

from ._admin_helpers import _record_sensitive_admin_read, _require_user

router = APIRouter()

_metering = MeteringService()


@router.get("/users/lookup-by-email", response_model=UserLookupResponse)
async def admin_lookup_user_by_email(
    request: Request,
    email: str = Query(..., description="Email address to look up."),
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == email))
    user = result.unique().scalar_one_or_none()
    if user is None:
        from treadstone.audit.services.audit import record_audit_event

        await record_audit_event(
            session,
            action="admin.user.lookup_by_email",
            target_type="user",
            result="failure",
            error_code="not_found",
            metadata={"email": email},
            request=request,
        )
        await session.commit()
        raise NotFoundError("User", email)
    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.user.lookup_by_email",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email},
    )
    await session.commit()
    return {"user_id": user.id, "email": user.email}


@router.post("/users/resolve-emails", response_model=ResolveEmailsResponse)
async def admin_resolve_emails(
    request: Request,
    body: ResolveEmailsRequest,
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    unique_emails = list(dict.fromkeys(body.emails))
    rows = await session.execute(select(User).where(User.email.in_(unique_emails)))
    user_map = {u.email: u for u in rows.unique().scalars().all()}
    results = []
    for email in body.emails:
        user = user_map.get(email)
        if user is None:
            results.append({"email": email, "user_id": None, "error": "User not found"})
        else:
            results.append({"email": email, "user_id": user.id, "error": None})
    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.user.resolve_emails",
        target_type="user_batch_lookup",
        metadata={
            "requested_count": len(body.emails),
            "unique_email_count": len(unique_emails),
            "resolved_count": sum(1 for item in results if item["user_id"] is not None),
        },
    )
    await session.commit()
    return {"results": results}


@router.get("/users/{user_id}/usage", response_model=UsageSummaryResponse)
async def admin_get_user_usage(
    user_id: str,
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    await _require_user(session, user_id)
    summary = await _metering.get_usage_summary(session, user_id)
    await session.commit()
    return summary


# ── Email Verification (Admin) ───────────────────────────────────────────────


def _require_non_production_email_backend() -> None:
    """Block verification-token endpoints in production (email_backend=resend)."""
    if settings.email_backend != "memory":
        raise NotFoundError("endpoint", "verification-token")


@router.get("/users/{user_id}/verification-token", include_in_schema=False)
async def get_user_verification_token(
    user_id: str,
    request: Request,
    admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Return the latest verification token for a user (admin only, non-production)."""
    _require_non_production_email_backend()

    target = await session.get(User, user_id)
    if not target:
        raise NotFoundError("User", user_id)

    latest = (
        await session.execute(
            select(EmailVerificationLog)
            .where(EmailVerificationLog.user_id == user_id)
            .order_by(EmailVerificationLog.gmt_created.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest is None:
        raise NotFoundError("verification token", user_id)

    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.verification_token.read",
        target_type="user",
        target_id=latest.user_id,
        metadata={"email": latest.email},
    )
    await session.commit()

    return {
        "user_id": latest.user_id,
        "email": latest.email,
        "token": latest.token,
        "verify_url": latest.verify_url,
        "created_at": latest.gmt_created,
    }


@router.get("/verification-token-by-email", include_in_schema=False)
async def get_verification_token_by_email(
    request: Request,
    email: str = Query(..., description="Email address to look up."),
    admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    """Return the latest verification token for an email (admin only, non-production).

    Available only when TREADSTONE_EMAIL_BACKEND=memory. Used by E2E tests.
    """
    _require_non_production_email_backend()

    latest = (
        await session.execute(
            select(EmailVerificationLog)
            .where(EmailVerificationLog.email == email)
            .order_by(EmailVerificationLog.gmt_created.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest is None:
        raise NotFoundError("verification token", email)

    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.verification_token.read",
        target_type="user",
        target_id=latest.user_id,
        metadata={"email": latest.email},
    )
    await session.commit()

    return {
        "user_id": latest.user_id,
        "email": latest.email,
        "token": latest.token,
        "verify_url": latest.verify_url,
        "created_at": latest.gmt_created,
    }
