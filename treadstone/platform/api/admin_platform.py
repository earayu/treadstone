"""Admin API — platform stats, limits, tier templates, waitlist, and feedback endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.schemas import (
    ComputeStats,
    FeedbackItemResponse,
    FeedbackListResponse,
    PlatformLimitsResponse,
    PlatformStatsResponse,
    SandboxStats,
    SandboxStatusCount,
    StorageStats,
    TierTemplateListResponse,
    UpdatePlatformLimitsRequest,
    UpdateTierTemplateRequest,
    UpdateTierTemplateResponse,
    UpdateWaitlistApplicationRequest,
    UserStats,
    WaitlistApplicationListResponse,
    WaitlistApplicationResponse,
)
from treadstone.audit.services.audit import record_audit_event
from treadstone.core.database import get_session
from treadstone.core.errors import ConflictError, NotFoundError
from treadstone.identity.api._admin_helpers import _record_sensitive_admin_read
from treadstone.identity.api.deps import get_current_admin, get_current_admin_session
from treadstone.identity.models.user import User, utc_now
from treadstone.metering.api.metering_serializers import serialize_template
from treadstone.metering.models.metering import StorageLedger, UserPlan
from treadstone.metering.services.metering_service import MeteringService
from treadstone.platform.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID
from treadstone.platform.models.user_feedback import UserFeedback
from treadstone.platform.models.waitlist import ApplicationStatus, WaitlistApplication
from treadstone.platform.services.platform_limits import PlatformLimitsService, PlatformLimitsSnapshot
from treadstone.sandbox.models.sandbox import Sandbox

router = APIRouter()

_metering = MeteringService()
_platform_limits = PlatformLimitsService()


def _sql_like_escape_fragment(value: str) -> str:
    """Escape `\\`, `%`, and `_` for use in PostgreSQL ILIKE with ESCAPE '\\'."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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


# ── Waitlist Applications (Admin) ─────────────────────────────────────────────


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


@router.patch("/waitlist/{application_id}", response_model=WaitlistApplicationResponse)
async def update_waitlist_application(
    application_id: str,
    body: UpdateWaitlistApplicationRequest,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> WaitlistApplicationResponse:
    """Approve or reject a waitlist application."""
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


# ── Support Feedback ────────────────────────────────────────────────────────


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
