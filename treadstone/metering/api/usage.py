"""Usage API — read-only endpoints for users to view their metering data.

Endpoints:
  GET /v1/usage                — aggregate usage overview
  GET /v1/usage/plan           — full UserPlan details
  GET /v1/usage/sessions       — paginated ComputeSession list
  GET /v1/usage/storage-ledger — paginated StorageLedger list
  GET /v1/usage/grants         — ComputeGrant and StorageQuotaGrant lists

Note: All endpoints call ``session.commit()`` because ``get_user_plan``
(called internally by ``get_usage_summary``, etc.) may lazily create a
UserPlan + welcome-bonus ComputeGrant on first access.  The commit
persists that side-effect.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.schemas import (
    ComputeSessionListResponse,
    GrantsResponse,
    StorageLedgerListResponse,
    UsageSummaryResponse,
    UserPlanResponse,
)
from treadstone.core.database import get_session
from treadstone.identity.api.deps import get_current_control_plane_user
from treadstone.identity.models.user import User, utc_now
from treadstone.metering.api.metering_serializers import (
    iso,
    serialize_compute_grant,
    serialize_plan,
    serialize_storage_quota_grant,
)
from treadstone.metering.models.metering import ComputeSession, StorageLedger
from treadstone.metering.services.metering_helpers import CU_MEMORY_WEIGHT, CU_VCPU_WEIGHT
from treadstone.metering.services.metering_service import MeteringService

router = APIRouter(prefix="/v1/usage", tags=["usage"])

_metering = MeteringService()


def _serialize_storage_state(storage_state: str) -> str:
    if storage_state == "deleted":
        return "released"
    return storage_state


def _serialize_session(cs: ComputeSession) -> dict:
    now = utc_now()
    end = cs.ended_at or now
    duration = (end - cs.started_at).total_seconds()
    cu_hours = float(CU_VCPU_WEIGHT * cs.vcpu_hours + CU_MEMORY_WEIGHT * cs.memory_gib_hours)
    return {
        "id": cs.id,
        "sandbox_id": cs.sandbox_id,
        "template": cs.template,
        "vcpu_request": float(cs.vcpu_request),
        "memory_gib_request": float(cs.memory_gib_request),
        "started_at": iso(cs.started_at),
        "ended_at": iso(cs.ended_at),
        "duration_seconds": duration,
        "compute_unit_hours": cu_hours,
        "vcpu_hours": float(cs.vcpu_hours),
        "memory_gib_hours": float(cs.memory_gib_hours),
        "status": "active" if cs.ended_at is None else "completed",
    }


@router.get("", response_model=UsageSummaryResponse)
async def get_usage(
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    summary = await _metering.get_usage_summary(session, user.id)
    await session.commit()
    return summary


@router.get("/plan", response_model=UserPlanResponse)
async def get_plan(
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    plan = await _metering.get_user_plan(session, user.id)
    await session.commit()
    return serialize_plan(plan)


@router.get("/sessions", response_model=ComputeSessionListResponse)
async def list_compute_sessions(
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
    status: str = Query(default="all", pattern="^(active|completed|all)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    await _metering.ensure_user_plan(session, user.id)
    items, total = await _metering.list_compute_sessions(session, user.id, status=status, limit=limit, offset=offset)
    await session.commit()
    return {
        "items": [_serialize_session(cs) for cs in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _serialize_storage_ledger(entry: StorageLedger) -> dict:
    return {
        "id": entry.id,
        "sandbox_id": entry.sandbox_id,
        "size_gib": entry.size_gib,
        "storage_state": _serialize_storage_state(entry.storage_state),
        "allocated_at": iso(entry.allocated_at),
        "released_at": iso(entry.released_at),
        "gib_hours_consumed": float(entry.gib_hours_consumed),
        "last_metered_at": iso(entry.last_metered_at),
    }


@router.get("/storage-ledger", response_model=StorageLedgerListResponse)
async def list_storage_ledger(
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
    status: str = Query(default="all", pattern="^(active|released|all)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    await _metering.ensure_user_plan(session, user.id)
    items, total = await _metering.list_storage_ledger(session, user.id, status=status, limit=limit, offset=offset)
    await session.commit()
    return {
        "items": [_serialize_storage_ledger(entry) for entry in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/grants", response_model=GrantsResponse)
async def list_grants(
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    await _metering.ensure_user_plan(session, user.id)
    compute_grants = await _metering.list_compute_grants(session, user.id)
    storage_grants = await _metering.list_storage_quota_grants(session, user.id)
    await session.commit()
    return {
        "compute_grants": [serialize_compute_grant(g) for g in compute_grants],
        "storage_quota_grants": [serialize_storage_quota_grant(g) for g in storage_grants],
    }
