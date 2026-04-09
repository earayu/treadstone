"""Background sandbox lifecycle tasks — idle auto-stop and scheduled auto-delete.

These run on the leader node via sync_supervisor's _lifecycle_tick_loop,
alongside (but independent of) metering tasks.

Module separation rationale:
  sandbox_service     — user-initiated lifecycle operations (request-path)
  sandbox_lifecycle   — periodic background lifecycle enforcement (leader-only)
  metering_tasks      — billing and quota enforcement (leader-only)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.models.audit_event import AuditActorType
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import utc_now
from treadstone.services.audit import record_audit_event
from treadstone.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

LIFECYCLE_TICK_INTERVAL = 60

StopSandboxCallback = Callable[[AsyncSession, Sandbox], Awaitable[None]]
DeleteSandboxCallback = Callable[[AsyncSession, Sandbox], Awaitable[None]]

_metering = MeteringService()


async def check_idle_auto_stop(
    session: AsyncSession,
    stop_callback: StopSandboxCallback | None = None,
) -> None:
    """Stop sandboxes that have been idle longer than their auto_stop_interval.

    Only considers READY sandboxes with a known gmt_last_active timestamp.
    Each sandbox is handled independently — a failure on one does not block others.
    """
    now = utc_now()
    result = await session.execute(
        select(Sandbox).where(
            Sandbox.status == SandboxStatus.READY,
            Sandbox.gmt_last_active.isnot(None),
            Sandbox.auto_stop_interval > 0,
        )
    )
    sandboxes = list(result.scalars().all())

    for sandbox in sandboxes:
        idle_seconds = (now - sandbox.gmt_last_active).total_seconds()
        threshold_seconds = sandbox.auto_stop_interval * 60
        sandbox_id = sandbox.id

        if idle_seconds <= threshold_seconds:
            continue

        try:
            async with session.begin_nested():
                if stop_callback is not None:
                    await stop_callback(session, sandbox)
                    # Eagerly mark STOPPED in DB so the next tick does not re-trigger
                    # before the K8s sync loop has a chance to update status.
                    if sandbox.status == SandboxStatus.READY:
                        sandbox.status = SandboxStatus.STOPPED
                        sandbox.gmt_stopped = utc_now()
                        sandbox.version += 1
                        session.add(sandbox)
                else:
                    await _db_only_stop(session, sandbox)
                await _metering.close_compute_session(session, sandbox.id)
                await record_audit_event(
                    session,
                    action="sandbox.idle_auto_stop",
                    target_type="sandbox",
                    target_id=sandbox.id,
                    actor_type=AuditActorType.SYSTEM.value,
                    metadata={
                        "owner_id": sandbox.owner_id,
                        "auto_stop_interval_minutes": sandbox.auto_stop_interval,
                        "idle_seconds": int(idle_seconds),
                    },
                )
                logger.info(
                    "Idle auto-stop: sandbox %s idle %.0fs > %ds threshold",
                    sandbox.id,
                    idle_seconds,
                    threshold_seconds,
                )
        except Exception:
            logger.exception("Failed to idle-auto-stop sandbox %s", sandbox_id)

    await session.commit()


async def check_auto_delete(
    session: AsyncSession,
    delete_callback: DeleteSandboxCallback | None = None,
) -> None:
    """Delete sandboxes that have been stopped longer than their auto_delete_interval.

    Only considers STOPPED sandboxes with auto_delete_interval > 0 and a known
    gmt_stopped timestamp.  Each sandbox is handled independently.
    """
    now = utc_now()
    result = await session.execute(
        select(Sandbox).where(
            Sandbox.status.in_([SandboxStatus.STOPPED, SandboxStatus.COLD]),
            Sandbox.pending_operation.is_(None),
            Sandbox.auto_delete_interval > 0,
            Sandbox.gmt_stopped.isnot(None),
        )
    )
    sandboxes = list(result.scalars().all())

    for sandbox in sandboxes:
        stopped_seconds = (now - sandbox.gmt_stopped).total_seconds()
        threshold_seconds = sandbox.auto_delete_interval * 60
        sandbox_id = sandbox.id

        if stopped_seconds <= threshold_seconds:
            continue

        try:
            async with session.begin_nested():
                if delete_callback is not None:
                    await delete_callback(session, sandbox)
                else:
                    await _db_only_delete(session, sandbox)
                await record_audit_event(
                    session,
                    action="sandbox.auto_delete",
                    target_type="sandbox",
                    target_id=sandbox.id,
                    actor_type=AuditActorType.SYSTEM.value,
                    metadata={
                        "owner_id": sandbox.owner_id,
                        "auto_delete_interval_minutes": sandbox.auto_delete_interval,
                        "stopped_seconds": int(stopped_seconds),
                    },
                )
                logger.info(
                    "Auto-delete: sandbox %s stopped %.0fs > %ds threshold",
                    sandbox.id,
                    stopped_seconds,
                    threshold_seconds,
                )
        except Exception:
            logger.exception("Failed to auto-delete sandbox %s", sandbox_id)

    await session.commit()


async def run_lifecycle_tick(
    session_factory: async_sessionmaker[AsyncSession],
    stop_sandbox_callback: StopSandboxCallback | None = None,
    delete_sandbox_callback: DeleteSandboxCallback | None = None,
) -> None:
    """Single lifecycle tick: idle auto-stop → auto-delete.

    Called every LIFECYCLE_TICK_INTERVAL seconds from the supervisor.
    Each sub-step gets its own session to isolate failures.
    """
    for step_name, step_fn in [
        ("check_idle_auto_stop", lambda s: check_idle_auto_stop(s, stop_sandbox_callback)),
        ("check_auto_delete", lambda s: check_auto_delete(s, delete_sandbox_callback)),
    ]:
        try:
            async with session_factory() as session:
                await step_fn(session)
        except Exception:
            logger.exception("Lifecycle tick step '%s' failed", step_name)


async def _db_only_stop(session: AsyncSession, sandbox: Sandbox) -> None:
    """Fallback stop when no K8s callback is available."""
    sandbox.status = SandboxStatus.STOPPED
    sandbox.gmt_stopped = utc_now()
    sandbox.version += 1
    session.add(sandbox)


async def _db_only_delete(session: AsyncSession, sandbox: Sandbox) -> None:
    """Fallback delete when no K8s callback is available."""
    prev_status = sandbox.status
    # When no K8s callback is available, finalize the DB state to avoid
    # leaving sandboxes stuck in DELETING indefinitely. If a CR still exists,
    # the periodic sync will reconcile it separately.
    sandbox.status = SandboxStatus.DELETED
    sandbox.gmt_deleted = utc_now()
    sandbox.version += 1
    session.add(sandbox)
    logger.info(
        "Sandbox %s status %s -> deleted (source=lifecycle_db_only_delete)",
        sandbox.id,
        prev_status,
    )
