"""K8s Watch + Reconciliation for Sandbox state sync.

Watches K8s Sandbox CRs for changes and updates the DB accordingly.
Runs periodic reconciliation as a fallback for missed Watch events.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.services.k8s_client import K8sClientProtocol

logger = logging.getLogger(__name__)

PHASE_TO_STATUS: dict[str, str] = {
    "Creating": SandboxStatus.CREATING,
    "Ready": SandboxStatus.READY,
    "Running": SandboxStatus.READY,
    "Stopped": SandboxStatus.STOPPED,
    "Error": SandboxStatus.ERROR,
    "Failed": SandboxStatus.ERROR,
    "Deleting": SandboxStatus.DELETING,
    "Deleted": SandboxStatus.DELETED,
}

RECONCILE_INTERVAL = 300  # 5 minutes


async def handle_watch_event(
    event_type: str,
    cr_object: dict,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Process a single K8s Watch event and update the DB."""
    cr_name = cr_object.get("metadata", {}).get("name")
    cr_namespace = cr_object.get("metadata", {}).get("namespace", "treadstone")
    cr_rv = cr_object.get("metadata", {}).get("resourceVersion")
    cr_phase = cr_object.get("status", {}).get("phase", "")
    new_status = PHASE_TO_STATUS.get(cr_phase)

    if not cr_name:
        return

    async with session_factory() as session:
        result = await session.execute(
            select(Sandbox).where(Sandbox.k8s_sandbox_name == cr_name, Sandbox.k8s_namespace == cr_namespace)
        )
        sandbox = result.scalar_one_or_none()

        if sandbox is None:
            logger.debug("Watch event for unknown CR %s/%s — ignoring", cr_namespace, cr_name)
            return

        if event_type == "DELETED":
            if sandbox.status == SandboxStatus.DELETING:
                target_status = SandboxStatus.DELETED
            else:
                logger.warning("Unexpected DELETED event for %s (status=%s), marking error", sandbox.id, sandbox.status)
                target_status = SandboxStatus.ERROR

            rows = await _optimistic_update(session, sandbox.id, sandbox.version, target_status, resource_version=cr_rv)
            if rows == 0:
                logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)
            return

        if event_type in ("ADDED", "MODIFIED") and new_status:
            if sandbox.status == new_status:
                if sandbox.k8s_resource_version != cr_rv:
                    await _update_sync_metadata(session, sandbox.id, cr_rv)
                return

            if not is_valid_transition(sandbox.status, new_status):
                logger.warning(
                    "Invalid transition %s -> %s for %s from Watch, skipping",
                    sandbox.status,
                    new_status,
                    sandbox.id,
                )
                return

            rows = await _optimistic_update(session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv)
            if rows == 0:
                logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)


async def reconcile(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """One-shot List + DB comparison for drift correction."""
    logger.info("Starting reconciliation for namespace %s", namespace)

    crs = await k8s_client.list_sandbox_crs(namespace)
    cr_map: dict[str, dict] = {}
    for cr in crs:
        name = cr.get("metadata", {}).get("name")
        if name:
            cr_map[name] = cr

    async with session_factory() as session:
        result = await session.execute(
            select(Sandbox).where(Sandbox.status != SandboxStatus.DELETED, Sandbox.k8s_namespace == namespace)
        )
        sandboxes = result.scalars().all()

        for sandbox in sandboxes:
            cr_key = sandbox.k8s_sandbox_name or sandbox.name
            cr = cr_map.pop(cr_key, None)

            if cr is None:
                if sandbox.status == SandboxStatus.DELETING:
                    await _optimistic_update(session, sandbox.id, sandbox.version, SandboxStatus.DELETED)
                elif sandbox.status != SandboxStatus.CREATING:
                    logger.warning("CR missing for %s (status=%s), marking error", sandbox.id, sandbox.status)
                    await _optimistic_update(session, sandbox.id, sandbox.version, SandboxStatus.ERROR)
                continue

            cr_rv = cr.get("metadata", {}).get("resourceVersion")
            if sandbox.k8s_resource_version == cr_rv:
                continue

            cr_phase = cr.get("status", {}).get("phase", "")
            new_status = PHASE_TO_STATUS.get(cr_phase)
            if new_status and new_status != sandbox.status and is_valid_transition(sandbox.status, new_status):
                await _optimistic_update(session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv)
            elif cr_rv != sandbox.k8s_resource_version:
                await _update_sync_metadata(session, sandbox.id, cr_rv)

    logger.info("Reconciliation complete. %d unmanaged CRs in K8s.", len(cr_map))


async def start_sync_loop(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run periodic reconciliation. Watch integration is deferred to real K8s client."""
    while True:
        try:
            await reconcile(namespace, k8s_client, session_factory)
        except Exception:
            logger.exception("Reconciliation failed")
        await asyncio.sleep(RECONCILE_INTERVAL)


async def _optimistic_update(
    session: AsyncSession,
    sandbox_id: str,
    expected_version: int,
    new_status: str,
    *,
    resource_version: str | None = None,
) -> int:
    """Update sandbox status with optimistic locking. Returns number of rows affected."""
    now = datetime.now(UTC)
    values: dict = {
        "status": new_status,
        "version": expected_version + 1,
        "last_synced_at": now,
    }
    if resource_version:
        values["k8s_resource_version"] = resource_version
    if new_status == SandboxStatus.READY:
        values["gmt_started"] = now
    elif new_status == SandboxStatus.STOPPED:
        values["gmt_stopped"] = now
    elif new_status == SandboxStatus.DELETED:
        values["gmt_deleted"] = now

    result = await session.execute(
        update(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.version == expected_version).values(**values)
    )
    await session.commit()
    return result.rowcount


async def _update_sync_metadata(session: AsyncSession, sandbox_id: str, resource_version: str) -> None:
    """Update only sync metadata without changing status."""
    await session.execute(
        update(Sandbox)
        .where(Sandbox.id == sandbox_id)
        .values(k8s_resource_version=resource_version, last_synced_at=datetime.now(UTC))
    )
    await session.commit()
