"""Shared serialization helpers for metering API routers (usage + admin)."""

from __future__ import annotations

from datetime import datetime

from treadstone.models.metering import CreditGrant, TierTemplate, UserPlan
from treadstone.models.user import utc_now


def iso(dt: datetime | None) -> str | None:
    """Convert a datetime to ISO-8601 string, or None."""
    return dt.isoformat() if dt is not None else None


def serialize_plan(plan: UserPlan) -> dict:
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "tier": plan.tier,
        "compute_credits_monthly_limit": float(plan.compute_credits_monthly_limit),
        "compute_credits_monthly_used": float(plan.compute_credits_monthly_used),
        "storage_capacity_limit_gib": plan.storage_capacity_limit_gib,
        "max_concurrent_running": plan.max_concurrent_running,
        "max_sandbox_duration_seconds": plan.max_sandbox_duration_seconds,
        "allowed_templates": plan.allowed_templates,
        "grace_period_seconds": plan.grace_period_seconds,
        "overrides": plan.overrides,
        "billing_period_start": iso(plan.period_start),
        "billing_period_end": iso(plan.period_end),
        "grace_period_started_at": iso(plan.grace_period_started_at),
        "warning_80_notified_at": iso(plan.warning_80_notified_at),
        "warning_100_notified_at": iso(plan.warning_100_notified_at),
        "created_at": iso(plan.gmt_created),
        "updated_at": iso(plan.gmt_updated),
    }


def serialize_template(tt: TierTemplate) -> dict:
    return {
        "tier": tt.tier_name,
        "compute_credits_monthly": float(tt.compute_credits_monthly),
        "storage_capacity_gib": tt.storage_capacity_gib,
        "max_concurrent_running": tt.max_concurrent_running,
        "max_sandbox_duration_seconds": tt.max_sandbox_duration_seconds,
        "allowed_templates": tt.allowed_templates,
        "grace_period_seconds": tt.grace_period_seconds,
        "is_active": tt.is_active,
        "created_at": iso(tt.gmt_created),
        "updated_at": iso(tt.gmt_updated),
    }


def grant_status(grant: CreditGrant) -> str:
    """Compute a virtual status field: active / exhausted / expired."""
    if grant.remaining_amount <= 0:
        return "exhausted"
    if grant.expires_at is not None:
        now = utc_now()
        expires = grant.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=now.tzinfo)
        if expires < now:
            return "expired"
    return "active"


def serialize_grant(grant: CreditGrant) -> dict:
    return {
        "id": grant.id,
        "credit_type": grant.credit_type,
        "grant_type": grant.grant_type,
        "original_amount": float(grant.original_amount),
        "remaining_amount": float(grant.remaining_amount),
        "reason": grant.reason,
        "granted_by": grant.granted_by,
        "campaign_id": grant.campaign_id,
        "status": grant_status(grant),
        "granted_at": iso(grant.granted_at),
        "expires_at": iso(grant.expires_at),
    }
