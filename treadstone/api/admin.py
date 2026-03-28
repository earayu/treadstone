"""Admin API — privileged endpoints for managing metering configuration and user plans.

Endpoints:
  GET    /v1/admin/tier-templates               — list all tier templates
  PATCH  /v1/admin/tier-templates/{tier_name}    — update a tier template
  GET    /v1/admin/users/lookup-by-email        — find user by email
  POST   /v1/admin/users/resolve-emails         — batch-resolve emails to user IDs
  GET    /v1/admin/users/{user_id}/usage         — view any user's usage summary
  PATCH  /v1/admin/users/{user_id}/plan          — change user tier / overrides
  POST   /v1/admin/users/{user_id}/grants        — issue extra credits to a user
  POST   /v1/admin/grants/batch                  — batch-issue extra credits
"""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_admin
from treadstone.api.metering_serializers import iso, serialize_plan, serialize_template
from treadstone.api.schemas import (
    BatchGrantRequest,
    BatchGrantResponse,
    CreateGrantRequest,
    CreateGrantResponse,
    ResolveEmailsRequest,
    ResolveEmailsResponse,
    TierTemplateListResponse,
    UpdatePlanRequest,
    UpdateTierTemplateRequest,
    UpdateTierTemplateResponse,
    UsageSummaryResponse,
    UserLookupResponse,
    UserPlanResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import NotFoundError
from treadstone.models.email_verification_log import EmailVerificationLog
from treadstone.models.user import User
from treadstone.services.audit import record_audit_event
from treadstone.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_metering = MeteringService()


# ── Tier Templates ───────────────────────────────────────────────────────────


@router.get("/tier-templates", response_model=TierTemplateListResponse)
async def list_tier_templates(
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    templates = await _metering.list_tier_templates(session)
    return {"items": [serialize_template(t) for t in templates]}


@router.patch("/tier-templates/{tier_name}", response_model=UpdateTierTemplateResponse)
async def update_tier_template(
    tier_name: str,
    body: UpdateTierTemplateRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    updates = body.model_dump(exclude_none=True, exclude={"apply_to_existing"})
    template, users_affected = await _metering.update_tier_template(
        session, tier_name, updates, apply_to_existing=body.apply_to_existing
    )

    await record_audit_event(
        session,
        action="admin.tier_template.updated",
        target_type="tier_template",
        target_id=tier_name,
        actor_user_id=admin.id,
        metadata={"updates": updates, "apply_to_existing": body.apply_to_existing, "users_affected": users_affected},
        request=request,
    )
    await session.commit()

    result = serialize_template(template)
    result["users_affected"] = users_affected
    return result


# ── User Lookup by Email ─────────────────────────────────────────────────────


@router.get("/users/lookup-by-email", response_model=UserLookupResponse)
async def admin_lookup_user_by_email(
    email: str = Query(..., description="Email address to look up."),
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == email))
    user = result.unique().scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", email)
    return {"user_id": user.id, "email": user.email}


@router.post("/users/resolve-emails", response_model=ResolveEmailsResponse)
async def admin_resolve_emails(
    body: ResolveEmailsRequest,
    _admin: User = Depends(get_current_admin),
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
    return {"results": results}


# ── User Usage (Admin View) ──────────────────────────────────────────────────


async def _require_user(session: AsyncSession, user_id: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.unique().scalar_one_or_none()
    if user is None:
        raise NotFoundError("User", user_id)
    return user


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


# ── User Plan (Admin Write) ─────────────────────────────────────────────────


@router.patch("/users/{user_id}/plan", response_model=UserPlanResponse)
async def admin_update_user_plan(
    user_id: str,
    body: UpdatePlanRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    await _require_user(session, user_id)

    plan = await _metering.get_user_plan(session, user_id)

    if body.tier is not None:
        plan = await _metering.update_user_tier(session, user_id, body.tier, overrides=body.overrides)
    elif body.overrides is not None:
        _metering.apply_overrides(plan, body.overrides)
        plan.overrides = {**(plan.overrides or {}), **body.overrides}
        session.add(plan)
        await session.flush()

    await record_audit_event(
        session,
        action="admin.user.plan_updated",
        target_type="user_plan",
        target_id=user_id,
        actor_user_id=admin.id,
        metadata={"tier": body.tier, "overrides": body.overrides},
        request=request,
    )
    await session.commit()
    return serialize_plan(plan)


# ── Grants (Single) ─────────────────────────────────────────────────────────


@router.post("/users/{user_id}/grants", response_model=CreateGrantResponse, status_code=201)
async def admin_create_grant(
    user_id: str,
    body: CreateGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    await _require_user(session, user_id)

    grant = await _metering.create_credit_grant(
        session,
        user_id,
        credit_type=body.credit_type,
        amount=Decimal(str(body.amount)),
        grant_type=body.grant_type,
        granted_by=admin.id,
        reason=body.reason,
        campaign_id=body.campaign_id,
        expires_at=body.expires_at,
    )

    await record_audit_event(
        session,
        action="metering.credits_granted",
        target_type="credit_grant",
        target_id=grant.id,
        actor_user_id=admin.id,
        metadata={
            "user_id": user_id,
            "credit_type": body.credit_type,
            "amount": body.amount,
            "grant_type": body.grant_type,
            "reason": body.reason,
        },
        request=request,
    )
    await session.commit()

    return {
        "id": grant.id,
        "user_id": grant.user_id,
        "credit_type": grant.credit_type,
        "original_amount": float(grant.original_amount),
        "remaining_amount": float(grant.remaining_amount),
        "grant_type": grant.grant_type,
        "reason": grant.reason,
        "granted_by": grant.granted_by,
        "campaign_id": grant.campaign_id,
        "granted_at": iso(grant.granted_at),
        "expires_at": iso(grant.expires_at),
    }


# ── Grants (Batch) ──────────────────────────────────────────────────────────


@router.post("/grants/batch", response_model=BatchGrantResponse)
async def admin_batch_grants(
    body: BatchGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    results: list[dict] = []
    succeeded = 0
    failed = 0

    for uid in body.user_ids:
        user_result = await session.execute(select(User).where(User.id == uid))
        if user_result.unique().scalar_one_or_none() is None:
            results.append({"user_id": uid, "grant_id": None, "status": "failed", "error": "User not found"})
            failed += 1
            continue

        try:
            async with session.begin_nested():
                grant = await _metering.create_credit_grant(
                    session,
                    uid,
                    credit_type=body.credit_type,
                    amount=Decimal(str(body.amount)),
                    grant_type=body.grant_type,
                    granted_by=admin.id,
                    reason=body.reason,
                    campaign_id=body.campaign_id,
                    expires_at=body.expires_at,
                )
                await record_audit_event(
                    session,
                    action="metering.credits_granted",
                    target_type="credit_grant",
                    target_id=grant.id,
                    actor_user_id=admin.id,
                    metadata={
                        "user_id": uid,
                        "credit_type": body.credit_type,
                        "amount": body.amount,
                        "grant_type": body.grant_type,
                        "campaign_id": body.campaign_id,
                        "reason": body.reason,
                    },
                    request=request,
                )
            results.append({"user_id": uid, "grant_id": grant.id, "status": "success", "error": None})
            succeeded += 1
        except Exception:
            logger.exception("Failed to create grant for user %s", uid)
            results.append({"user_id": uid, "grant_id": None, "status": "failed", "error": "Internal error"})
            failed += 1

    await session.commit()

    return {
        "total_requested": len(body.user_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


# ── Email Verification (Admin) ───────────────────────────────────────────────


def _require_non_production_email_backend() -> None:
    """Block verification-token endpoints in production (email_backend=resend)."""
    if settings.email_backend != "memory":
        raise NotFoundError("endpoint", "verification-token")


@router.get("/users/{user_id}/verification-token", include_in_schema=False)
async def get_user_verification_token(
    user_id: str,
    admin: User = Depends(get_current_admin),
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

    return {
        "user_id": latest.user_id,
        "email": latest.email,
        "token": latest.token,
        "verify_url": latest.verify_url,
        "created_at": latest.gmt_created,
    }


@router.get("/verification-token-by-email", include_in_schema=False)
async def get_verification_token_by_email(
    email: str = Query(..., description="Email address to look up."),
    admin: User = Depends(get_current_admin),
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

    return {
        "user_id": latest.user_id,
        "email": latest.email,
        "token": latest.token,
        "verify_url": latest.verify_url,
        "created_at": latest.gmt_created,
    }
