"""Admin API — metering plan and grant management endpoints."""

from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.schemas import (
    BatchComputeGrantRequest,
    BatchGrantResponse,
    BatchStorageQuotaGrantRequest,
    CreateComputeGrantRequest,
    CreateComputeGrantResponse,
    CreateStorageQuotaGrantRequest,
    CreateStorageQuotaGrantResponse,
    UpdatePlanRequest,
    UserPlanResponse,
)
from treadstone.audit.services.audit import record_audit_event
from treadstone.core.database import get_session
from treadstone.identity.api._admin_helpers import _load_existing_user_ids, _require_user
from treadstone.identity.api.deps import get_current_admin
from treadstone.identity.models.user import User
from treadstone.metering.api.metering_serializers import (
    serialize_compute_grant,
    serialize_plan,
    serialize_storage_quota_grant,
)
from treadstone.metering.models.metering import ComputeGrant, StorageQuotaGrant
from treadstone.metering.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

router = APIRouter()

_metering = MeteringService()


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
