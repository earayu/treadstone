"""Admin API — privileged endpoints for managing metering configuration and user plans.

Endpoints:
  GET    /v1/admin/stats                        — platform-level operational statistics
  GET    /v1/admin/platform-limits              — read platform-wide global cap configuration
  PATCH  /v1/admin/platform-limits              — update platform-wide global cap configuration
  GET    /v1/admin/tier-templates               — list all tier templates
  PATCH  /v1/admin/tier-templates/{tier_name}    — update a tier template
  GET    /v1/admin/users/lookup-by-email        — find user by email
  POST   /v1/admin/users/resolve-emails         — batch-resolve emails to user IDs
  GET    /v1/admin/users/{user_id}/usage         — view any user's usage summary
  PATCH  /v1/admin/users/{user_id}/plan          — change user tier / overrides
  POST   /v1/admin/users/{user_id}/compute-grants   — issue compute credits grant
  POST   /v1/admin/users/{user_id}/storage-grants  — issue storage quota grant
  POST   /v1/admin/compute-grants/batch           — batch-issue compute grants
  POST   /v1/admin/storage-grants/batch           — batch-issue storage quota grants
  GET    /v1/admin/support/feedback               — list user-submitted support feedback
  POST   /v1/admin/sandboxes/{sandbox_id}/force-reset-pending  — force-clear stuck pending_operation
"""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_admin, get_current_admin_session
from treadstone.api.metering_serializers import (
    serialize_compute_grant,
    serialize_plan,
    serialize_storage_quota_grant,
    serialize_template,
)
from treadstone.api.schemas import (
    BatchComputeGrantRequest,
    BatchGrantResponse,
    BatchStorageQuotaGrantRequest,
    ComputeStats,
    CreateComputeGrantRequest,
    CreateComputeGrantResponse,
    CreateStorageQuotaGrantRequest,
    CreateStorageQuotaGrantResponse,
    FeedbackItemResponse,
    FeedbackListResponse,
    PlatformLimitsResponse,
    PlatformStatsResponse,
    ResolveEmailsRequest,
    ResolveEmailsResponse,
    SandboxStats,
    SandboxStatusCount,
    StorageStats,
    TierTemplateListResponse,
    UpdatePlanRequest,
    UpdatePlatformLimitsRequest,
    UpdateTierTemplateRequest,
    UpdateTierTemplateResponse,
    UpdateWaitlistApplicationRequest,
    UsageSummaryResponse,
    UserLookupResponse,
    UserPlanResponse,
    UserStats,
    WaitlistApplicationListResponse,
    WaitlistApplicationResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import ConflictError, NotFoundError
from treadstone.models.email_verification_log import EmailVerificationLog
from treadstone.models.metering import ComputeGrant, StorageLedger, StorageQuotaGrant, UserPlan
from treadstone.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User, utc_now
from treadstone.models.user_feedback import UserFeedback
from treadstone.models.waitlist import ApplicationStatus, WaitlistApplication
from treadstone.services.audit import record_audit_event
from treadstone.services.metering_service import MeteringService
from treadstone.services.platform_limits import PlatformLimitsService, PlatformLimitsSnapshot

logger = logging.getLogger(__name__)


def _sql_like_escape_fragment(value: str) -> str:
    """Escape `\\`, `%`, and `_` for use in PostgreSQL ILIKE with ESCAPE '\\'."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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


async def _load_existing_user_ids(session: AsyncSession, user_ids: list[str]) -> set[str]:
    """Resolve batch user existence with a single query."""
    unique_user_ids = {user_id for user_id in user_ids}
    if not unique_user_ids:
        return set()

    result = await session.execute(select(User.id).where(User.id.in_(unique_user_ids)))
    return set(result.scalars().all())


router = APIRouter(prefix="/v1/admin", tags=["admin"])

_metering = MeteringService()
_platform_limits = PlatformLimitsService()


def serialize_compute_grant_response(grant: ComputeGrant) -> dict:
    base = serialize_compute_grant(grant)
    return {
        "id": base["id"],
        "user_id": grant.user_id,
        "original_amount": base["original_amount"],
        "remaining_amount": base["remaining_amount"],
        "grant_type": base["grant_type"],
        "reason": base["reason"],
        "granted_by": base["granted_by"],
        "campaign_id": base["campaign_id"],
        "granted_at": base["granted_at"],
        "expires_at": base["expires_at"],
    }


def serialize_storage_quota_grant_response(grant: StorageQuotaGrant) -> dict:
    base = serialize_storage_quota_grant(grant)
    return {
        "id": base["id"],
        "user_id": grant.user_id,
        "size_gib": base["size_gib"],
        "grant_type": base["grant_type"],
        "reason": base["reason"],
        "granted_by": base["granted_by"],
        "campaign_id": base["campaign_id"],
        "granted_at": base["granted_at"],
        "expires_at": base["expires_at"],
    }


def _serialize_platform_limits(snapshot: PlatformLimitsSnapshot) -> dict:
    return {
        "config": {
            "max_registered_users": snapshot.config.max_registered_users,
            "max_total_sandboxes": snapshot.config.max_total_sandboxes,
            "max_total_storage_gib": snapshot.config.max_total_storage_gib,
            "max_waitlist_applications": snapshot.config.max_waitlist_applications,
        },
        "usage": {
            "registered_users": snapshot.usage.registered_users,
            "total_sandboxes": snapshot.usage.total_sandboxes,
            "total_storage_gib": snapshot.usage.total_storage_gib,
            "waitlist_applications": snapshot.usage.waitlist_applications,
        },
        "refreshed_at": snapshot.refreshed_at,
    }


# ── Platform Stats ───────────────────────────────────────────────────────────


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    _admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> PlatformStatsResponse:
    """Return aggregated platform-level operational statistics."""

    # User stats
    user_row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(User.is_active.is_(True)).label("active"),
                func.count().filter(User.role == "admin").label("admin_count"),
            )
        )
    ).one()
    users = UserStats(total=user_row.total, active=user_row.active, admin_count=user_row.admin_count)

    # Sandbox stats — one query grouped by status
    sandbox_rows = (
        await session.execute(select(Sandbox.status, func.count().label("cnt")).group_by(Sandbox.status))
    ).all()
    status_breakdown = [SandboxStatusCount(status=row.status, count=row.cnt) for row in sandbox_rows]
    total_created = sum(row.count for row in status_breakdown)
    currently_running = next((row.count for row in status_breakdown if row.status == "ready"), 0)
    sandboxes = SandboxStats(
        total_created=total_created,
        currently_running=currently_running,
        status_breakdown=status_breakdown,
    )

    # Compute stats — sum of current-period CU usage across all user plans
    cu_row = (await session.execute(select(func.coalesce(func.sum(UserPlan.compute_units_monthly_used), 0)))).scalar()
    compute = ComputeStats(total_cu_hours_this_period=float(cu_row))

    # Storage stats — active ledger entries for allocated GiB, all entries for consumed GiB-hours
    storage_row = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(StorageLedger.size_gib).filter(StorageLedger.storage_state == "active"), 0
                ).label("allocated_gib"),
                func.coalesce(func.sum(StorageLedger.gib_hours_consumed), 0).label("consumed_gib_hours"),
            )
        )
    ).one()
    storage = StorageStats(
        total_allocated_gib=float(storage_row.allocated_gib),
        total_consumed_gib_hours=float(storage_row.consumed_gib_hours),
    )

    return PlatformStatsResponse(users=users, sandboxes=sandboxes, compute=compute, storage=storage)


# ── Platform Limits ───────────────────────────────────────────────────────────


@router.get("/platform-limits", response_model=PlatformLimitsResponse)
async def get_platform_limits(
    request: Request,
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
) -> PlatformLimitsResponse:
    snapshot = await _platform_limits.build_snapshot(session)
    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.platform_limits.read",
        target_type="platform_limits",
        target_id=PLATFORM_LIMITS_SINGLETON_ID,
        metadata=_serialize_platform_limits(snapshot)["config"],
    )
    await session.commit()
    return _serialize_platform_limits(snapshot)


@router.patch("/platform-limits", response_model=PlatformLimitsResponse)
async def update_platform_limits(
    body: UpdatePlatformLimitsRequest,
    request: Request,
    admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
) -> PlatformLimitsResponse:
    config = await _platform_limits.get_or_create_config(session)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(config, field, value)
    config.gmt_updated = utc_now()
    session.add(config)
    await record_audit_event(
        session,
        action="admin.platform_limits.updated",
        target_type="platform_limits",
        target_id=config.id,
        actor_user_id=admin.id,
        metadata={"updates": updates},
        request=request,
    )
    await session.commit()
    snapshot = await request.app.state.platform_limits_runtime.refresh_from_session(session)
    return _serialize_platform_limits(snapshot)


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
    request: Request,
    email: str = Query(..., description="Email address to look up."),
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == email))
    user = result.unique().scalar_one_or_none()
    if user is None:
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


@router.post("/users/{user_id}/compute-grants", response_model=CreateComputeGrantResponse, status_code=201)
async def admin_create_compute_grant(
    user_id: str,
    body: CreateComputeGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    await _require_user(session, user_id)
    grant = await _metering.create_compute_grant(
        session,
        user_id,
        amount=Decimal(str(body.amount)),
        grant_type=body.grant_type,
        granted_by=admin.id,
        reason=body.reason,
        campaign_id=body.campaign_id,
        expires_at=body.expires_at,
    )
    await record_audit_event(
        session,
        action="metering.compute_grant_created",
        target_type="compute_grant",
        target_id=grant.id,
        actor_user_id=admin.id,
        metadata={"user_id": user_id, "amount": body.amount, "grant_type": body.grant_type, "reason": body.reason},
        request=request,
    )
    await session.commit()
    return serialize_compute_grant_response(grant)


@router.post("/users/{user_id}/storage-grants", response_model=CreateStorageQuotaGrantResponse, status_code=201)
async def admin_create_storage_grant(
    user_id: str,
    body: CreateStorageQuotaGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    await _require_user(session, user_id)
    grant = await _metering.create_storage_quota_grant(
        session,
        user_id,
        size_gib=body.size_gib,
        grant_type=body.grant_type,
        granted_by=admin.id,
        reason=body.reason,
        campaign_id=body.campaign_id,
        expires_at=body.expires_at,
    )
    await record_audit_event(
        session,
        action="metering.storage_quota_grant_created",
        target_type="storage_quota_grant",
        target_id=grant.id,
        actor_user_id=admin.id,
        metadata={
            "user_id": user_id,
            "size_gib": body.size_gib,
            "grant_type": body.grant_type,
            "reason": body.reason,
        },
        request=request,
    )
    await session.commit()
    return serialize_storage_quota_grant_response(grant)


# ── Grants (Batch) ──────────────────────────────────────────────────────────


@router.post("/compute-grants/batch", response_model=BatchGrantResponse)
async def admin_batch_compute_grants(
    body: BatchComputeGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    results: list[dict] = []
    succeeded = 0
    failed = 0
    existing_user_ids = await _load_existing_user_ids(session, body.user_ids)

    for uid in body.user_ids:
        if uid not in existing_user_ids:
            results.append({"user_id": uid, "grant_id": None, "status": "failed", "error": "User not found"})
            failed += 1
            continue

        try:
            async with session.begin_nested():
                grant = await _metering.create_compute_grant(
                    session,
                    uid,
                    amount=Decimal(str(body.amount)),
                    grant_type=body.grant_type,
                    granted_by=admin.id,
                    reason=body.reason,
                    campaign_id=body.campaign_id,
                    expires_at=body.expires_at,
                )
                await record_audit_event(
                    session,
                    action="metering.compute_grant_created",
                    target_type="compute_grant",
                    target_id=grant.id,
                    actor_user_id=admin.id,
                    metadata={
                        "user_id": uid,
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
            logger.exception("Failed to create compute grant for user %s", uid)
            results.append({"user_id": uid, "grant_id": None, "status": "failed", "error": "Internal error"})
            failed += 1

    await session.commit()

    return {
        "total_requested": len(body.user_ids),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@router.post("/storage-grants/batch", response_model=BatchGrantResponse)
async def admin_batch_storage_grants(
    body: BatchStorageQuotaGrantRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    results: list[dict] = []
    succeeded = 0
    failed = 0
    existing_user_ids = await _load_existing_user_ids(session, body.user_ids)

    for uid in body.user_ids:
        if uid not in existing_user_ids:
            results.append({"user_id": uid, "grant_id": None, "status": "failed", "error": "User not found"})
            failed += 1
            continue

        try:
            async with session.begin_nested():
                grant = await _metering.create_storage_quota_grant(
                    session,
                    uid,
                    size_gib=body.size_gib,
                    grant_type=body.grant_type,
                    granted_by=admin.id,
                    reason=body.reason,
                    campaign_id=body.campaign_id,
                    expires_at=body.expires_at,
                )
                await record_audit_event(
                    session,
                    action="metering.storage_quota_grant_created",
                    target_type="storage_quota_grant",
                    target_id=grant.id,
                    actor_user_id=admin.id,
                    metadata={
                        "user_id": uid,
                        "size_gib": body.size_gib,
                        "grant_type": body.grant_type,
                        "campaign_id": body.campaign_id,
                        "reason": body.reason,
                    },
                    request=request,
                )
            results.append({"user_id": uid, "grant_id": grant.id, "status": "success", "error": None})
            succeeded += 1
        except Exception:
            logger.exception("Failed to create storage quota grant for user %s", uid)
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


# ── Waitlist Applications (Admin) ─────────────────────────────────────────────


def _serialize_waitlist_application(app: WaitlistApplication) -> dict:
    return {
        "id": app.id,
        "email": app.email,
        "name": app.name,
        "target_tier": app.target_tier,
        "company": app.company,
        "github_or_portfolio_url": app.github_or_portfolio_url,
        "use_case": app.use_case,
        "status": app.status,
        "processed_at": app.processed_at,
        "gmt_created": app.gmt_created,
    }


@router.get("/waitlist", response_model=WaitlistApplicationListResponse)
async def list_waitlist_applications(
    request: Request,
    tier: str | None = Query(default=None, description="Filter by target tier (pro, ultra)"),
    status: str | None = Query(default=None, description="Filter by status (pending, approved, rejected)"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
) -> WaitlistApplicationListResponse:
    """List waitlist applications with optional filters."""
    from sqlalchemy import func

    query = select(WaitlistApplication)
    count_query = select(func.count()).select_from(WaitlistApplication)

    if tier:
        query = query.where(WaitlistApplication.target_tier == tier.lower())
        count_query = count_query.where(WaitlistApplication.target_tier == tier.lower())
    if status:
        query = query.where(WaitlistApplication.status == status.lower())
        count_query = count_query.where(WaitlistApplication.status == status.lower())

    total = (await session.execute(count_query)).scalar_one()
    rows = (
        (await session.execute(query.order_by(WaitlistApplication.gmt_created.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.waitlist.read",
        target_type="waitlist_application",
        metadata={"tier": tier, "status": status, "limit": limit, "offset": offset, "result_count": len(rows)},
    )
    await session.commit()

    return {"items": [_serialize_waitlist_application(r) for r in rows], "total": total}


@router.get("/support/feedback", response_model=FeedbackListResponse)
async def list_user_feedback(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    email: str | None = Query(
        default=None,
        description="Optional case-insensitive substring match on submitter email.",
    ),
    _admin: User = Depends(get_current_admin_session),
    session: AsyncSession = Depends(get_session),
) -> FeedbackListResponse:
    """List user-submitted support feedback (newest first)."""
    count_query = select(func.count()).select_from(UserFeedback)
    query = select(UserFeedback)
    trimmed_email = email.strip() if email else None
    if trimmed_email:
        pattern = f"%{_sql_like_escape_fragment(trimmed_email)}%"
        email_filter = UserFeedback.email.ilike(pattern, escape="\\")
        count_query = count_query.where(email_filter)
        query = query.where(email_filter)

    total = (await session.execute(count_query)).scalar_one()
    rows = (
        (await session.execute(query.order_by(UserFeedback.gmt_created.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    items = [
        FeedbackItemResponse(
            id=r.id,
            user_id=r.user_id,
            email=r.email,
            body=r.body,
            gmt_created=r.gmt_created,
        )
        for r in rows
    ]
    await _record_sensitive_admin_read(
        session,
        request=request,
        action="admin.feedback.read",
        target_type="user_feedback",
        metadata={
            "email_filter": trimmed_email,
            "limit": limit,
            "offset": offset,
            "result_count": len(items),
        },
    )
    await session.commit()
    return FeedbackListResponse(items=items, total=total)


@router.patch("/waitlist/{application_id}", response_model=WaitlistApplicationResponse)
async def update_waitlist_application(
    application_id: str,
    body: UpdateWaitlistApplicationRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> WaitlistApplicationResponse:
    """Approve or reject a waitlist application."""
    from treadstone.models.user import utc_now

    app = (
        await session.execute(select(WaitlistApplication).where(WaitlistApplication.id == application_id))
    ).scalar_one_or_none()

    if app is None:
        raise NotFoundError("WaitlistApplication", application_id)

    if app.status != ApplicationStatus.PENDING:
        raise ConflictError(
            f"This application is already {app.status} and cannot be updated. "
            "Only pending applications can be approved or rejected."
        )

    app.status = body.status
    app.processed_at = utc_now()
    app.gmt_updated = utc_now()

    await record_audit_event(
        session,
        action="admin.waitlist.updated",
        target_type="waitlist_application",
        target_id=application_id,
        actor_user_id=admin.id,
        metadata={"status": body.status, "email": app.email, "target_tier": app.target_tier},
        request=request,
    )
    await session.commit()
    await session.refresh(app)

    return _serialize_waitlist_application(app)


# ── Sandbox Operations ────────────────────────────────────────────────────────


@router.post("/sandboxes/{sandbox_id}/force-reset-pending")
async def admin_force_reset_pending(
    sandbox_id: str,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Force-clear a stuck ``pending_operation`` on a sandbox.

    Currently only supports resetting ``snapshotting``.  Restoring operations
    may have already materialized K8s resources (Sandbox CR, PVC) which cannot
    be safely cleaned up by a simple status reset; those require manual
    intervention or waiting for the restore to converge.
    """
    from treadstone.models.sandbox import Sandbox, SandboxPendingOperation, SandboxStatus

    sandbox = await session.get(Sandbox, sandbox_id)
    if sandbox is None or sandbox.gmt_deleted is not None:
        raise NotFoundError("Sandbox", sandbox_id)

    if sandbox.pending_operation is None:
        return {
            "id": sandbox.id,
            "status": sandbox.status,
            "pending_operation": None,
            "message": "No-op: no pending operation to reset.",
        }

    if sandbox.pending_operation != SandboxPendingOperation.SNAPSHOTTING:
        raise ConflictError(
            f"Only 'snapshotting' can be force-reset. "
            f"This sandbox has pending_operation={sandbox.pending_operation!r} which may have "
            f"materialized K8s resources that require manual cleanup."
        )

    prev_pending = sandbox.pending_operation
    prev_status = sandbox.status

    sandbox.pending_operation = None
    sandbox.status = SandboxStatus.STOPPED
    sandbox.status_message = f"Force-reset by admin from pending_operation={prev_pending}"
    sandbox.version += 1
    session.add(sandbox)

    await record_audit_event(
        session,
        action="admin.sandbox.force_reset_pending",
        target_type="sandbox",
        target_id=sandbox_id,
        actor_user_id=admin.id,
        metadata={
            "previous_status": prev_status,
            "previous_pending_operation": prev_pending,
            "new_status": sandbox.status,
            "owner_id": sandbox.owner_id,
        },
        request=request,
    )
    await session.commit()

    return {
        "id": sandbox.id,
        "status": sandbox.status,
        "pending_operation": sandbox.pending_operation,
        "message": f"Reset pending_operation={prev_pending}; status {prev_status} -> {sandbox.status}",
    }
