"""Background metering tasks — periodic compute/storage tick, grace period enforcement,
warning notifications, and monthly reset.

These functions are designed to run on the leader node via sync_supervisor's
_metering_tick_loop.  Each function accepts an AsyncSession (or session_factory)
and commits its own transactions.

Module separation rationale:
  MeteringService  — core CRUD, quota checks, credit consumption (request-path)
  metering_tasks   — periodic background operations (leader-only tick path)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import Numeric, cast, func, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.audit.models.audit_event import AuditActorType
from treadstone.audit.services.audit import record_audit_event
from treadstone.identity.models.user import utc_now
from treadstone.metering.models.metering import ComputeGrant, ComputeSession, StorageLedger, StorageState, UserPlan
from treadstone.metering.services.metering_helpers import calculate_cu_rate
from treadstone.metering.services.metering_service import MeteringService
from treadstone.sandbox.models.sandbox import Sandbox, SandboxStatus

logger = logging.getLogger(__name__)

__all__ = [
    "TICK_INTERVAL",
    "ABSOLUTE_OVERAGE_CAP_RATIO",
    "run_metering_tick",
    "tick_metering",
    "tick_storage_metering",
    "check_grace_periods",
    "check_warning_thresholds",
    "handle_period_rollover",
    "reset_monthly_credits",
]

TICK_INTERVAL = 60
ABSOLUTE_OVERAGE_CAP_RATIO = Decimal("0.20")

StopSandboxCallback = Callable[[AsyncSession, Sandbox], Awaitable[None]]

_metering = MeteringService()


class _OptimisticLockConflict(Exception):
    """Raised inside a savepoint to trigger rollback on lock conflict."""


@dataclass(slots=True)
class _UserMeteringSnapshot:
    plan: UserPlan
    extra_compute_remaining: Decimal
    total_remaining: Decimal


_SANDBOX_UNSET = object()


# ═══════════════════════════════════════════════════════════
#  F18 — tick_metering (compute incremental metering)
# ═══════════════════════════════════════════════════════════


async def tick_metering(session: AsyncSession) -> int:
    """Accumulate raw resource-hours for all open ComputeSessions and consume credits.

    Each session update runs inside a savepoint so that an optimistic-lock
    conflict rolls back only that single session, not the entire tick batch.

    After accumulating raw hours, computes credit deltas per user using
    ``calculate_cu_rate()`` and consumes them from the dual pool
    (monthly first, then ComputeGrant FIFO).

    Returns the number of sessions successfully metered.
    """
    now = utc_now()

    result = await session.execute(select(ComputeSession).where(ComputeSession.ended_at.is_(None)))
    open_sessions = result.scalars().all()

    metered = 0
    user_credit_deltas: dict[str, Decimal] = {}

    for cs in open_sessions:
        elapsed_seconds = (now - cs.last_metered_at).total_seconds()
        if elapsed_seconds <= 0:
            continue

        elapsed_hours = Decimal(str(elapsed_seconds)) / Decimal("3600")
        delta_vcpu_hours = cs.vcpu_request * elapsed_hours
        delta_memory_gib_hours = cs.memory_gib_request * elapsed_hours

        try:
            async with session.begin_nested():
                rows = await session.execute(
                    update(ComputeSession)
                    .where(
                        ComputeSession.id == cs.id,
                        ComputeSession.gmt_updated == cs.gmt_updated,
                    )
                    .values(
                        vcpu_hours=ComputeSession.vcpu_hours + delta_vcpu_hours,
                        memory_gib_hours=ComputeSession.memory_gib_hours + delta_memory_gib_hours,
                        last_metered_at=now,
                        gmt_updated=now,
                    )
                )

                if rows.rowcount == 0:
                    raise _OptimisticLockConflict()
        except _OptimisticLockConflict:
            logger.debug(
                "Optimistic lock conflict for ComputeSession %s, skipping this tick",
                cs.id,
            )
            continue

        cu_rate = calculate_cu_rate(cs.template)
        cu_delta = cu_rate * elapsed_hours
        user_credit_deltas[cs.user_id] = user_credit_deltas.get(cs.user_id, Decimal("0")) + cu_delta
        metered += 1

    for user_id, total_delta in user_credit_deltas.items():
        if total_delta > Decimal("0"):
            await _metering.consume_compute_credits(session, user_id, total_delta)

    if metered > 0:
        await session.commit()
    return metered


# ═══════════════════════════════════════════════════════════
#  F19 — tick_storage_metering (GiB-hours accumulation)
# ═══════════════════════════════════════════════════════════


async def tick_storage_metering(session: AsyncSession) -> int:
    """Update gib_hours_consumed for all ACTIVE StorageLedger entries.

    Uses a single bulk UPDATE instead of loading all rows into Python.
    Returns the number of entries updated.
    """
    now = utc_now()

    elapsed_seconds = func.extract("epoch", literal(now) - StorageLedger.last_metered_at)
    increment = func.round(
        cast(
            StorageLedger.size_gib * elapsed_seconds / 3600,
            Numeric(10, 4),
        ),
        4,
    )

    stmt = (
        update(StorageLedger)
        .where(
            StorageLedger.storage_state == StorageState.ACTIVE,
            StorageLedger.last_metered_at < now,
        )
        .values(
            gib_hours_consumed=StorageLedger.gib_hours_consumed + increment,
            last_metered_at=now,
            gmt_updated=now,
        )
    )
    result = await session.execute(stmt)
    updated = result.rowcount

    if updated > 0:
        await session.commit()

    return updated


# ═══════════════════════════════════════════════════════════
#  F22 — Warning threshold notifications
# ═══════════════════════════════════════════════════════════


async def check_warning_thresholds(session: AsyncSession) -> None:
    """Detect 80% and 100% compute usage thresholds and emit audit events.

    Uses ``warning_80_notified_at`` / ``warning_100_notified_at`` on UserPlan
    for per-period deduplication — each warning fires at most once per billing
    period (fields are cleared on monthly reset).

    When a user jumps from <80% to >100% in a single tick, only the 100%
    warning fires; 80% fires on the next tick.  This is intentional — the
    100% signal is more urgent.
    """
    user_ids = await _get_users_with_running_sandboxes(session)
    snapshots = await _load_user_metering_snapshots(session, user_ids)

    for user_id in user_ids:
        snapshot = snapshots.get(user_id)
        if snapshot is None:
            continue

        plan = snapshot.plan
        total_remaining = snapshot.total_remaining

        monthly_limit = plan.compute_units_monthly_limit
        monthly_used = plan.compute_units_monthly_used
        extra_remaining = snapshot.extra_compute_remaining

        # 100% warning: monthly + extra fully exhausted
        if total_remaining <= Decimal("0") and plan.warning_100_notified_at is None:
            plan.warning_100_notified_at = utc_now()
            plan.gmt_updated = utc_now()
            session.add(plan)
            await record_audit_event(
                session,
                action="metering.compute_warning_100",
                target_type="user",
                target_id=user_id,
                actor_type=AuditActorType.SYSTEM.value,
                metadata={
                    "tier": plan.tier,
                    "monthly_used": float(monthly_used),
                    "monthly_limit": float(monthly_limit),
                    "extra_remaining": float(extra_remaining),
                    "total_remaining": float(total_remaining),
                },
            )

        # 80% warning: monthly pool >= 80% used (regardless of extra pool)
        elif (
            monthly_limit > Decimal("0")
            and monthly_used >= monthly_limit * Decimal("0.8")
            and plan.warning_80_notified_at is None
        ):
            plan.warning_80_notified_at = utc_now()
            plan.gmt_updated = utc_now()
            session.add(plan)
            await record_audit_event(
                session,
                action="metering.compute_warning_80",
                target_type="user",
                target_id=user_id,
                actor_type=AuditActorType.SYSTEM.value,
                metadata={
                    "tier": plan.tier,
                    "monthly_used": float(monthly_used),
                    "monthly_limit": float(monthly_limit),
                    "extra_remaining": float(extra_remaining),
                    "total_remaining": float(total_remaining),
                },
            )

    await session.commit()


# ═══════════════════════════════════════════════════════════
#  F21 — Grace Period state machine + auto-stop
# ═══════════════════════════════════════════════════════════


async def check_grace_periods(
    session: AsyncSession,
    stop_sandbox_callback: StopSandboxCallback | None = None,
) -> None:
    """Evaluate grace-period state for every user with running sandboxes.

    State machine:
      normal → grace_period_started (first detection of exhaustion)
      grace_period → enforcement (timer expired OR absolute cap exceeded)
      any → normal (credits restored, e.g. admin grant)

    ``stop_sandbox_callback`` is an async callable ``(session, sandbox) -> None``
    that scales the sandbox to 0.  When None, a DB-only fallback is used
    (marks sandbox as STOPPED and closes the ComputeSession; K8s will be
    corrected by reconcile).
    """
    user_ids = await _get_users_with_running_sandboxes(session)
    snapshots = await _load_user_metering_snapshots(session, user_ids)
    running_sandboxes_by_user = await _get_running_sandboxes_by_user(session, user_ids)

    for user_id in user_ids:
        snapshot = snapshots.get(user_id)
        if snapshot is None:
            continue

        plan = snapshot.plan
        total_remaining = snapshot.total_remaining

        if total_remaining <= Decimal("0"):
            await _handle_exhausted(
                session,
                plan,
                user_id,
                total_remaining,
                stop_sandbox_callback,
                running_sandboxes=running_sandboxes_by_user.get(user_id, []),
            )
        else:
            await _handle_credits_restored(session, plan, user_id, total_remaining)

    await session.commit()


async def _handle_exhausted(
    session: AsyncSession,
    plan: UserPlan,
    user_id: str,
    total_remaining: Decimal,
    stop_callback: StopSandboxCallback | None,
    *,
    running_sandboxes: list[Sandbox] | None = None,
) -> None:
    """Handle a user whose credits are fully exhausted."""
    now = utc_now()

    if plan.grace_period_started_at is None:
        plan.grace_period_started_at = now
        plan.gmt_updated = now
        session.add(plan)
        await record_audit_event(
            session,
            action="metering.grace_period_started",
            target_type="user",
            target_id=user_id,
            actor_type=AuditActorType.SYSTEM.value,
            metadata={
                "tier": plan.tier,
                "grace_period_seconds": plan.grace_period_seconds,
                "monthly_used": float(plan.compute_units_monthly_used),
                "monthly_limit": float(plan.compute_units_monthly_limit),
            },
        )
        return

    elapsed = (now - plan.grace_period_started_at).total_seconds()

    overage = abs(total_remaining)
    absolute_cap = plan.compute_units_monthly_limit * ABSOLUTE_OVERAGE_CAP_RATIO
    exceeded_absolute_cap = overage > absolute_cap

    if elapsed > plan.grace_period_seconds or exceeded_absolute_cap:
        reason = "absolute_cap_exceeded" if exceeded_absolute_cap else "grace_period_expired"
        await _enforce_stop(
            session,
            plan,
            user_id,
            reason,
            elapsed,
            overage,
            stop_callback,
            running_sandboxes=running_sandboxes,
        )


async def _enforce_stop(
    session: AsyncSession,
    plan: UserPlan,
    user_id: str,
    reason: str,
    grace_elapsed_seconds: float,
    overage: Decimal,
    stop_callback: StopSandboxCallback | None,
    *,
    running_sandboxes: list[Sandbox] | None = None,
) -> None:
    """Force-stop all running sandboxes for a user (grace period enforcement).

    Closes ComputeSession for each successfully stopped sandbox to prevent
    continued billing.  Metering close and audit writes are best-effort here:
    the authoritative enforcement outcome is whether any sandboxes remain in a
    running state after this pass. If none remain, clear grace state so the
    user plan does not stay stuck in grace due to follow-up failures that
    existing repair loops can reconcile later.
    """
    sandboxes = running_sandboxes if running_sandboxes is not None else await _get_running_sandboxes(session, user_id)

    for sandbox in sandboxes:
        try:
            if stop_callback is not None:
                await stop_callback(session, sandbox)
            else:
                await _db_only_stop(session, sandbox)
        except Exception:
            logger.exception("Failed to force-stop sandbox %s during grace enforcement", sandbox.id)
            continue

        try:
            await _metering.close_compute_session(session, sandbox.id)
        except Exception:
            logger.exception(
                "Failed to close compute session for sandbox %s during grace enforcement",
                sandbox.id,
            )

        try:
            await record_audit_event(
                session,
                action="metering.auto_stop",
                target_type="sandbox",
                target_id=sandbox.id,
                actor_type=AuditActorType.SYSTEM.value,
                metadata={
                    "user_id": user_id,
                    "tier": plan.tier,
                    "reason": reason,
                    "grace_elapsed_seconds": int(grace_elapsed_seconds),
                    "overage_compute_units": float(overage),
                },
            )
        except Exception:
            logger.exception("Failed to record auto-stop audit event for sandbox %s", sandbox.id)

    remaining_running = await _get_running_sandboxes(session, user_id)
    if not remaining_running:
        plan.grace_period_started_at = None
        plan.gmt_updated = utc_now()
        session.add(plan)


async def _handle_credits_restored(
    session: AsyncSession,
    plan: UserPlan,
    user_id: str,
    total_remaining: Decimal,
) -> None:
    """Clear grace period when credits are restored (e.g. admin grant)."""
    if plan.grace_period_started_at is None:
        return

    plan.grace_period_started_at = None
    plan.gmt_updated = utc_now()
    session.add(plan)
    await record_audit_event(
        session,
        action="metering.grace_period_cleared",
        target_type="user",
        target_id=user_id,
        actor_type=AuditActorType.SYSTEM.value,
        metadata={
            "tier": plan.tier,
            "total_remaining": float(total_remaining),
        },
    )


async def _db_only_stop(session: AsyncSession, sandbox: Sandbox) -> None:
    """Fallback stop: update DB status and close ComputeSession.

    K8s reconcile will catch up on the actual pod scaling.
    """
    sandbox.status = SandboxStatus.STOPPED
    sandbox.gmt_stopped = utc_now()
    sandbox.version += 1
    session.add(sandbox)
    await _metering.close_compute_session(session, sandbox.id)


# ═══════════════════════════════════════════════════════════
#  F23 — Monthly reset + cross-month session splitting
# ═══════════════════════════════════════════════════════════


async def handle_period_rollover(
    session: AsyncSession,
    cs: ComputeSession,
    plan: UserPlan,
    *,
    sandbox: Sandbox | None | object = _SANDBOX_UNSET,
) -> ComputeSession | None:
    """Split a ComputeSession at the billing period boundary.

    Closes the old session at ``period_end``, resets monthly credits,
    and opens a new session from the new period start if the sandbox
    is still running.

    Returns the new ComputeSession (or None if the sandbox is no longer READY).
    """
    now = utc_now()
    if now <= plan.period_end:
        return None

    period_boundary = plan.period_end

    # 1. Close old session at period boundary — accrue final slice of resource-hours
    elapsed = (period_boundary - cs.last_metered_at).total_seconds()
    if elapsed > 0:
        elapsed_hours = Decimal(str(elapsed)) / Decimal("3600")
        cs.vcpu_hours += cs.vcpu_request * elapsed_hours
        cs.memory_gib_hours += cs.memory_gib_request * elapsed_hours

    cs.ended_at = period_boundary
    cs.last_metered_at = period_boundary
    cs.gmt_updated = now
    session.add(cs)

    # 2. Reset monthly credits and advance period
    new_period_start = period_boundary
    new_period_end = period_boundary + relativedelta(months=1)

    plan.compute_units_monthly_used = Decimal("0")
    plan.compute_units_overage = Decimal("0")
    plan.period_start = new_period_start
    plan.period_end = new_period_end
    plan.warning_80_notified_at = None
    plan.warning_100_notified_at = None
    plan.grace_period_started_at = None
    plan.gmt_updated = now
    session.add(plan)

    await record_audit_event(
        session,
        action="metering.monthly_reset",
        target_type="user",
        target_id=cs.user_id,
        actor_type=AuditActorType.SYSTEM.value,
        metadata={
            "tier": plan.tier,
            "old_period_end": period_boundary.isoformat(),
            "new_period_end": new_period_end.isoformat(),
        },
    )

    # 3. If sandbox still running, create a new session for the new period
    if sandbox is _SANDBOX_UNSET:
        sandbox = await session.get(Sandbox, cs.sandbox_id)
    if sandbox is None or sandbox.status != SandboxStatus.READY:
        await session.flush()
        return None

    new_cs = ComputeSession(
        sandbox_id=cs.sandbox_id,
        user_id=cs.user_id,
        template=cs.template,
        vcpu_request=cs.vcpu_request,
        memory_gib_request=cs.memory_gib_request,
        started_at=new_period_start,
        last_metered_at=new_period_start,
        vcpu_hours=Decimal("0"),
        memory_gib_hours=Decimal("0"),
    )
    session.add(new_cs)
    await session.flush()
    return new_cs


async def reset_monthly_credits(session: AsyncSession) -> int:
    """Bulk-reset monthly credits for all users whose period has ended.

    Handles cross-month session splitting for any open ComputeSessions.
    Uses a while loop per plan to catch up multiple missed months in a
    single tick (e.g. after prolonged leader downtime).
    Returns the number of user plans reset.
    """
    now = utc_now()

    result = await session.execute(select(UserPlan).where(UserPlan.period_end <= now))
    plans = result.scalars().all()
    sessions_by_user = await _get_open_sessions_by_user(session, [plan.user_id for plan in plans])
    sandbox_by_id = await _get_sandboxes_by_id(
        session,
        [cs.sandbox_id for sessions in sessions_by_user.values() for cs in sessions],
    )

    reset_count = 0
    for plan in plans:
        while plan.period_end <= now:
            next_open_sessions: list[ComputeSession] = []
            for cs in sessions_by_user.get(plan.user_id, []):
                new_session = await handle_period_rollover(
                    session,
                    cs,
                    plan,
                    sandbox=sandbox_by_id.get(cs.sandbox_id),
                )
                if new_session is not None:
                    next_open_sessions.append(new_session)
            sessions_by_user[plan.user_id] = next_open_sessions

            if plan.period_end <= now:
                new_period_start = plan.period_end
                new_period_end = plan.period_end + relativedelta(months=1)

                plan.compute_units_monthly_used = Decimal("0")
                plan.compute_units_overage = Decimal("0")
                plan.period_start = new_period_start
                plan.period_end = new_period_end
                plan.warning_80_notified_at = None
                plan.warning_100_notified_at = None
                plan.grace_period_started_at = None
                plan.gmt_updated = now
                session.add(plan)

                await record_audit_event(
                    session,
                    action="metering.monthly_reset",
                    target_type="user",
                    target_id=plan.user_id,
                    actor_type=AuditActorType.SYSTEM.value,
                    metadata={
                        "tier": plan.tier,
                        "old_period_end": new_period_start.isoformat(),
                        "new_period_end": new_period_end.isoformat(),
                    },
                )

        reset_count += 1

    if reset_count > 0:
        await session.commit()

    return reset_count


# ═══════════════════════════════════════════════════════════
#  F20 — Unified tick entry point for sync_supervisor
# ═══════════════════════════════════════════════════════════


async def run_metering_tick(
    session_factory: async_sessionmaker[AsyncSession],
    stop_sandbox_callback: StopSandboxCallback | None = None,
) -> None:
    """Single tick: compute metering → storage metering → warnings → grace → monthly reset.

    Called every TICK_INTERVAL seconds from the supervisor's _metering_tick_loop.
    Each sub-step gets its own session to isolate failures.
    """
    for step_name, step_fn in [
        ("tick_metering", lambda s: tick_metering(s)),
        ("tick_storage_metering", lambda s: tick_storage_metering(s)),
        ("check_warning_thresholds", lambda s: check_warning_thresholds(s)),
        ("check_grace_periods", lambda s: check_grace_periods(s, stop_sandbox_callback)),
        ("reset_monthly_credits", lambda s: reset_monthly_credits(s)),
    ]:
        try:
            async with session_factory() as session:
                await step_fn(session)
        except Exception:
            logger.exception("Metering tick step '%s' failed", step_name)


# ═══════════════════════════════════════════════════════════
#  Query helpers (shared across tasks)
# ═══════════════════════════════════════════════════════════


async def _get_users_with_open_sessions(session: AsyncSession) -> list[str]:
    """Return distinct user_ids that have at least one open ComputeSession."""
    result = await session.execute(select(ComputeSession.user_id).where(ComputeSession.ended_at.is_(None)).distinct())
    return [row[0] for row in result.all()]


async def _get_users_with_running_sandboxes(session: AsyncSession) -> list[str]:
    """Return distinct user_ids with sandboxes in CREATING or READY status."""
    result = await session.execute(
        select(Sandbox.owner_id).where(Sandbox.status.in_([SandboxStatus.CREATING, SandboxStatus.READY])).distinct()
    )
    return [row[0] for row in result.all()]


async def _load_user_metering_snapshots(
    session: AsyncSession,
    user_ids: list[str],
) -> dict[str, _UserMeteringSnapshot]:
    """Batch-load plan and grant state for users touched by a metering tick."""
    if not user_ids:
        return {}

    result = await session.execute(select(UserPlan).where(UserPlan.user_id.in_(user_ids)))
    plans_by_user = {plan.user_id: plan for plan in result.scalars().all()}

    missing_user_ids = [user_id for user_id in user_ids if user_id not in plans_by_user]
    for user_id in missing_user_ids:
        plans_by_user[user_id] = await _metering.get_user_plan(session, user_id)

    now = utc_now()
    grants_result = await session.execute(
        select(
            ComputeGrant.user_id,
            func.coalesce(func.sum(ComputeGrant.remaining_amount), 0),
        )
        .where(
            ComputeGrant.user_id.in_(user_ids),
            ComputeGrant.remaining_amount > 0,
            or_(
                ComputeGrant.expires_at.is_(None),
                ComputeGrant.expires_at > now,
            ),
        )
        .group_by(ComputeGrant.user_id)
    )
    extra_remaining_by_user = {
        user_id: Decimal(str(remaining_amount)) for user_id, remaining_amount in grants_result.all()
    }

    snapshots: dict[str, _UserMeteringSnapshot] = {}
    for user_id in user_ids:
        plan = plans_by_user[user_id]
        extra_remaining = extra_remaining_by_user.get(user_id, Decimal("0"))
        total_remaining = (
            plan.compute_units_monthly_limit
            - plan.compute_units_monthly_used
            + extra_remaining
            - (plan.compute_units_overage or Decimal("0"))
        )
        snapshots[user_id] = _UserMeteringSnapshot(
            plan=plan,
            extra_compute_remaining=extra_remaining,
            total_remaining=total_remaining,
        )
    return snapshots


async def _get_running_sandboxes(session: AsyncSession, user_id: str) -> list[Sandbox]:
    """Return all CREATING/READY sandboxes for the given user."""
    result = await session.execute(
        select(Sandbox).where(
            Sandbox.owner_id == user_id,
            Sandbox.status.in_([SandboxStatus.CREATING, SandboxStatus.READY]),
        )
    )
    return list(result.scalars().all())


async def _get_running_sandboxes_by_user(session: AsyncSession, user_ids: list[str]) -> dict[str, list[Sandbox]]:
    """Return running sandboxes for a set of users using one grouped query."""
    if not user_ids:
        return {}

    result = await session.execute(
        select(Sandbox).where(
            Sandbox.owner_id.in_(user_ids),
            Sandbox.status.in_([SandboxStatus.CREATING, SandboxStatus.READY]),
        )
    )
    sandboxes_by_user: dict[str, list[Sandbox]] = defaultdict(list)
    for sandbox in result.scalars().all():
        sandboxes_by_user[sandbox.owner_id].append(sandbox)
    return dict(sandboxes_by_user)


async def _get_open_sessions_by_user(session: AsyncSession, user_ids: list[str]) -> dict[str, list[ComputeSession]]:
    """Return open compute sessions grouped by user in one query."""
    if not user_ids:
        return {}

    result = await session.execute(
        select(ComputeSession).where(
            ComputeSession.user_id.in_(user_ids),
            ComputeSession.ended_at.is_(None),
        )
    )
    sessions_by_user: dict[str, list[ComputeSession]] = defaultdict(list)
    for compute_session in result.scalars().all():
        sessions_by_user[compute_session.user_id].append(compute_session)
    return dict(sessions_by_user)


async def _get_sandboxes_by_id(session: AsyncSession, sandbox_ids: list[str]) -> dict[str, Sandbox]:
    """Return sandboxes keyed by id for rollover checks."""
    if not sandbox_ids:
        return {}

    result = await session.execute(select(Sandbox).where(Sandbox.id.in_(sandbox_ids)))
    return {sandbox.id: sandbox for sandbox in result.scalars().all()}
