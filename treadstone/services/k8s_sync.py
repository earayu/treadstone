"""K8s Watch + Reconciliation for Sandbox state sync.

Watches K8s Sandbox CRs for changes and updates the DB accordingly.
Runs periodic reconciliation as a fallback for missed Watch events.

Status derivation from real Sandbox CR (agents.x-k8s.io):
  - conditions[type=Ready].status == "True" + replicas == 1  → READY
  - conditions[type=Ready].status == "True" + replicas == 0  → STOPPED
  - conditions[type=Ready].reason == "ReconcilerError"       → ERROR
  - conditions[type=Ready].reason == "SandboxExpired"        → STOPPED
  - conditions[type=Ready].reason == "DependenciesNotReady"  → CREATING
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.config import settings
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.services.k8s_client import K8sClientProtocol, WatchExpiredError

logger = logging.getLogger(__name__)

RECONCILE_INTERVAL = 300  # 5 minutes
WATCH_RESTART_BACKOFF = 5  # seconds to wait before restarting Watch after unexpected failure


def derive_status_from_sandbox_cr(cr: dict) -> tuple[str, str]:
    """Derive Treadstone SandboxStatus from a real Sandbox CR's status + spec.

    Returns (status, message).
    """
    spec_replicas = cr.get("spec", {}).get("replicas", 1)
    conditions = cr.get("status", {}).get("conditions", [])

    ready_cond = None
    for c in conditions:
        if c.get("type") == "Ready":
            ready_cond = c
            break

    if ready_cond is None:
        return SandboxStatus.CREATING, "No Ready condition yet"

    cond_status = ready_cond.get("status", "Unknown")
    reason = ready_cond.get("reason", "")
    message = ready_cond.get("message", "")

    if reason == "SandboxExpired":
        return SandboxStatus.STOPPED, "Sandbox expired"

    if reason == "ReconcilerError":
        return SandboxStatus.ERROR, message

    if cond_status == "True":
        if spec_replicas == 0:
            return SandboxStatus.STOPPED, "Replicas scaled to 0"
        return SandboxStatus.READY, message

    if reason == "DependenciesNotReady":
        if spec_replicas == 0:
            return SandboxStatus.STOPPED, "Replicas scaled to 0"
        return SandboxStatus.CREATING, message

    return SandboxStatus.CREATING, message


async def handle_watch_event(
    event_type: str,
    cr_object: dict,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Process a single K8s Watch event and update the DB."""
    cr_name = cr_object.get("metadata", {}).get("name")
    cr_namespace = cr_object.get("metadata", {}).get("namespace", settings.sandbox_namespace)
    cr_rv = cr_object.get("metadata", {}).get("resourceVersion")

    if not cr_name:
        return

    async with session_factory() as session:
        result = await session.execute(
            select(Sandbox).where(
                ((Sandbox.k8s_sandbox_name == cr_name) | (Sandbox.k8s_sandbox_claim_name == cr_name)),
                Sandbox.k8s_namespace == cr_namespace,
            )
        )
        sandbox = result.scalar_one_or_none()

        if sandbox is None:
            logger.debug("Watch event for unknown CR %s/%s — ignoring", cr_namespace, cr_name)
            return

        if event_type == "DELETED":
            if sandbox.status == SandboxStatus.DELETING:
                await _delete_sandbox_row(session, sandbox.id)
            else:
                logger.warning("Unexpected DELETED event for %s (status=%s), marking error", sandbox.id, sandbox.status)
                rows = await _optimistic_update(
                    session, sandbox.id, sandbox.version, SandboxStatus.ERROR, resource_version=cr_rv
                )
                if rows == 0:
                    logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)
            return

        if event_type in ("ADDED", "MODIFIED"):
            new_status, message = derive_status_from_sandbox_cr(cr_object)

            dirty = False
            if sandbox.k8s_sandbox_name is None:
                sandbox.k8s_sandbox_name = cr_name
                dirty = True

            service_fqdn = cr_object.get("status", {}).get("serviceFQDN", "")
            if service_fqdn and sandbox.endpoints.get("service_fqdn") != service_fqdn:
                sandbox.endpoints = {**sandbox.endpoints, "service_fqdn": service_fqdn}
                dirty = True

            if dirty:
                session.add(sandbox)
                await session.flush()

            if sandbox.status == new_status:
                if sandbox.k8s_resource_version != cr_rv:
                    await _update_sync_metadata(session, sandbox.id, cr_rv, message)
                return

            if not is_valid_transition(sandbox.status, new_status):
                logger.warning(
                    "Invalid transition %s -> %s for %s from Watch, skipping",
                    sandbox.status,
                    new_status,
                    sandbox.id,
                )
                return

            rows = await _optimistic_update(
                session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv, message=message
            )
            if rows == 0:
                logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)


async def reconcile(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """One-shot List + DB comparison for drift correction.

    Returns the list-level resourceVersion, which can be used as a starting point for Watch.
    """
    logger.info("Starting reconciliation for namespace %s", namespace)

    list_response = await k8s_client.list_sandboxes_with_metadata(namespace)
    list_rv = list_response.get("metadata", {}).get("resourceVersion", "")
    sandbox_crs = list_response.get("items", [])

    cr_map: dict[str, dict] = {}
    for cr in sandbox_crs:
        name = cr.get("metadata", {}).get("name")
        if name:
            cr_map[name] = cr

    async with session_factory() as session:
        result = await session.execute(select(Sandbox).where(Sandbox.k8s_namespace == namespace))
        sandboxes = result.scalars().all()

        for sandbox in sandboxes:
            cr_key = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
            cr = cr_map.pop(cr_key, None)

            if cr is None:
                if sandbox.status == SandboxStatus.DELETING:
                    await _delete_sandbox_row(session, sandbox.id)
                elif sandbox.status != SandboxStatus.CREATING:
                    logger.warning("CR missing for %s (status=%s), marking error", sandbox.id, sandbox.status)
                    await _optimistic_update(session, sandbox.id, sandbox.version, SandboxStatus.ERROR)
                continue

            cr_rv = cr.get("metadata", {}).get("resourceVersion")
            if sandbox.k8s_resource_version == cr_rv:
                continue

            new_status, message = derive_status_from_sandbox_cr(cr)

            if new_status != sandbox.status and is_valid_transition(sandbox.status, new_status):
                await _optimistic_update(
                    session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv, message=message
                )
            elif cr_rv != sandbox.k8s_resource_version:
                await _update_sync_metadata(session, sandbox.id, cr_rv, message)

    logger.info("Reconciliation complete. %d unmanaged CRs in K8s. list_rv=%s", len(cr_map), list_rv)
    return list_rv


async def watch_loop(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
    resource_version: str,
) -> None:
    """Consume Watch events and update DB in real time. Raises WatchExpiredError on 410."""
    logger.info("Watch loop starting from rv=%s", resource_version)
    async for event_type, cr_object in k8s_client.watch_sandboxes(namespace, resource_version):
        try:
            await handle_watch_event(event_type, cr_object, session_factory)
        except Exception:
            logger.exception("Error handling Watch event for %s", cr_object.get("metadata", {}).get("name"))
        rv = cr_object.get("metadata", {}).get("resourceVersion", "")
        if rv:
            resource_version = rv
    logger.info("Watch stream ended (server closed connection)")


async def _periodic_reconcile(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Periodic reconciliation as a safety net alongside Watch."""
    while True:
        await asyncio.sleep(RECONCILE_INTERVAL)
        try:
            await reconcile(namespace, k8s_client, session_factory)
        except Exception:
            logger.exception("Periodic reconciliation failed")


async def start_sync_loop(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Run Watch + periodic reconciliation concurrently.

    On startup and after each Watch failure: reconcile (List) to get a consistent
    resourceVersion, then start Watch from that point. Periodic reconciliation
    runs as a safety net to catch any missed Watch events.
    """
    try:
        while True:
            try:
                list_rv = await reconcile(namespace, k8s_client, session_factory)
            except Exception:
                logger.exception("Initial reconciliation failed, retrying in %ds", WATCH_RESTART_BACKOFF)
                await asyncio.sleep(WATCH_RESTART_BACKOFF)
                continue

            reconcile_task = asyncio.create_task(_periodic_reconcile(namespace, k8s_client, session_factory))
            try:
                await watch_loop(namespace, k8s_client, session_factory, list_rv)
                # Watch stream ended normally (server timeout) — restart
                logger.info("Watch stream ended, restarting")
            except WatchExpiredError:
                logger.info("Watch resourceVersion expired (410), re-listing")
            except Exception:
                logger.exception("Watch loop failed, restarting in %ds", WATCH_RESTART_BACKOFF)
                await asyncio.sleep(WATCH_RESTART_BACKOFF)
            finally:
                reconcile_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await reconcile_task
    except asyncio.CancelledError:
        logger.info("Sync loop shutting down")


async def _optimistic_update(
    session: AsyncSession,
    sandbox_id: str,
    expected_version: int,
    new_status: str,
    *,
    resource_version: str | None = None,
    message: str | None = None,
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
    if message is not None:
        values["status_message"] = message
    if new_status == SandboxStatus.READY:
        values["gmt_started"] = now
    elif new_status == SandboxStatus.STOPPED:
        values["gmt_stopped"] = now
    result = await session.execute(
        update(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.version == expected_version).values(**values)
    )
    await session.commit()
    return result.rowcount


async def _update_sync_metadata(
    session: AsyncSession, sandbox_id: str, resource_version: str, message: str | None = None
) -> None:
    """Update only sync metadata without changing status."""
    values: dict = {"k8s_resource_version": resource_version, "last_synced_at": datetime.now(UTC)}
    if message is not None:
        values["status_message"] = message
    await session.execute(update(Sandbox).where(Sandbox.id == sandbox_id).values(**values))
    await session.commit()


async def _delete_sandbox_row(session: AsyncSession, sandbox_id: str) -> None:
    sandbox = await session.get(Sandbox, sandbox_id)
    if sandbox is None:
        return
    await session.delete(sandbox)
    await session.commit()
