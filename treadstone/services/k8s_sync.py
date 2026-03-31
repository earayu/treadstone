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

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.config import settings
from treadstone.models.audit_event import AuditActorType
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.services.audit import record_audit_event
from treadstone.services.k8s_client import K8sClientProtocol, WatchExpiredError
from treadstone.services.metering_helpers import sync_template_specs_from_k8s, validate_template_specs
from treadstone.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

_metering = MeteringService()

RECONCILE_INTERVAL = 300  # 5 minutes
WATCH_RESTART_BACKOFF = 5  # seconds to wait before restarting Watch after unexpected failure


def _reconcile_tried_cr_keys(sandbox: Sandbox) -> str:
    """Build a comma-separated list of CR name candidates for logging (List snapshot lookup)."""
    keys: list[str] = []
    for k in (sandbox.k8s_sandbox_name, sandbox.k8s_sandbox_claim_name, sandbox.id):
        if k and k not in keys:
            keys.append(k)
    return ", ".join(keys)


def _pop_sandbox_cr_for_reconcile(cr_map: dict[str, dict], sandbox: Sandbox) -> dict | None:
    """Pop the Sandbox CR from the List response keyed by ``metadata.name``.

    ``handle_watch_event`` matches rows when the event's CR name equals either
    ``k8s_sandbox_name`` or ``k8s_sandbox_claim_name``. Reconcile tries those names in the
    same order, and additionally ``sandbox.id`` when the CR's ``metadata.name`` is the
    sandbox id (e.g. direct provisioning) — Watch does not query by ``id``, but List keys
    may still be the id string.
    """
    for k in (sandbox.k8s_sandbox_name, sandbox.k8s_sandbox_claim_name, sandbox.id):
        if k and k in cr_map:
            return cr_map.pop(k)
    return None


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
                Sandbox.gmt_deleted.is_(None),
            )
        )
        sandbox = result.scalar_one_or_none()

        if sandbox is None:
            logger.debug("Watch event for unknown CR %s/%s — ignoring", cr_namespace, cr_name)
            return

        if event_type == "DELETED":
            await _try_close_compute_session(session, sandbox.id)
            if sandbox.persist:
                await _try_release_storage_ledger(session, sandbox.id)
            if sandbox.status == SandboxStatus.DELETING:
                await _record_status_change(
                    session,
                    sandbox_id=sandbox.id,
                    from_status=sandbox.status,
                    to_status="deleted",
                    source="k8s_watch",
                )
                await _delete_sandbox_row(session, sandbox.id)
            else:
                logger.warning(
                    "Unexpected DELETED (Watch): sandbox_id=%s db_status=%s cr=%s/%s rv=%s — marking error",
                    sandbox.id,
                    sandbox.status,
                    cr_namespace,
                    cr_name,
                    cr_rv,
                )
                rows = await _optimistic_update(
                    session, sandbox.id, sandbox.version, SandboxStatus.ERROR, resource_version=cr_rv
                )
                if rows == 0:
                    logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)
                else:
                    await _record_status_change(
                        session,
                        sandbox_id=sandbox.id,
                        from_status=sandbox.status,
                        to_status=SandboxStatus.ERROR,
                        source="k8s_watch",
                    )
                    await session.commit()
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
                    "Invalid transition (Watch): sandbox_id=%s db_status=%s -> k8s_derived=%s cr=%s/%s rv=%s "
                    "cr_message=%r — skipping (state machine)",
                    sandbox.id,
                    sandbox.status,
                    new_status,
                    cr_namespace,
                    cr_name,
                    cr_rv,
                    message,
                )
                return

            old_status = sandbox.status
            rows = await _optimistic_update(
                session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv, message=message
            )
            if rows == 0:
                logger.debug("Optimistic lock conflict for %s, skipping", sandbox.id)
            else:
                await _record_status_change(
                    session,
                    sandbox_id=sandbox.id,
                    from_status=old_status,
                    to_status=new_status,
                    source="k8s_watch",
                    message=message,
                )
                await _apply_metering_on_transition(session, sandbox, old_status, new_status)
                await session.commit()


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
        result = await session.execute(
            select(Sandbox).where(Sandbox.k8s_namespace == namespace, Sandbox.gmt_deleted.is_(None))
        )
        sandboxes = result.scalars().all()

        for sandbox in sandboxes:
            cr = _pop_sandbox_cr_for_reconcile(cr_map, sandbox)
            tried_keys = _reconcile_tried_cr_keys(sandbox)

            if cr is None:
                if sandbox.status == SandboxStatus.DELETING:
                    await _try_close_compute_session(session, sandbox.id)
                    if sandbox.persist:
                        await _try_release_storage_ledger(session, sandbox.id)
                    await _record_status_change(
                        session,
                        sandbox_id=sandbox.id,
                        from_status=sandbox.status,
                        to_status="deleted",
                        source="k8s_reconcile",
                    )
                    await _delete_sandbox_row(session, sandbox.id)
                elif sandbox.status == SandboxStatus.STOPPED:
                    logger.warning(
                        "CR missing (reconcile List): sandbox_id=%s db_status=stopped tried_cr_keys=%s ns=%s; "
                        "not marking error — list snapshot may be incomplete; if CR was actually deleted, "
                        "see this warning in logs/metrics",
                        sandbox.id,
                        tried_keys,
                        sandbox.k8s_namespace,
                    )
                elif sandbox.status != SandboxStatus.CREATING:
                    logger.warning(
                        "CR missing (reconcile List): sandbox_id=%s db_status=%s tried_cr_keys=%s ns=%s; "
                        "CR not in list snapshot (lag, name mismatch, or consistency) — marking error",
                        sandbox.id,
                        sandbox.status,
                        tried_keys,
                        sandbox.k8s_namespace,
                    )
                    old_status = sandbox.status
                    rows = await _optimistic_update(session, sandbox.id, sandbox.version, SandboxStatus.ERROR)
                    if rows == 0:
                        logger.debug(
                            "Optimistic lock conflict for reconcile (CR missing -> error) sandbox_id=%s, skipping",
                            sandbox.id,
                        )
                    else:
                        await _record_status_change(
                            session,
                            sandbox_id=sandbox.id,
                            from_status=old_status,
                            to_status=SandboxStatus.ERROR,
                            source="k8s_reconcile",
                        )
                        await _apply_metering_on_transition(session, sandbox, old_status, SandboxStatus.ERROR)
                        await session.commit()
                continue

            cr_rv = cr.get("metadata", {}).get("resourceVersion")
            new_status, message = derive_status_from_sandbox_cr(cr)

            # Skip only when both the resource version AND the derived status already
            # match what is stored in the DB.  Checking resource version alone is not
            # enough: a previous Watch event may have stored the resource version but
            # failed to update the status (e.g. due to an optimistic-lock conflict or
            # because the transition was previously blocked by the state machine).
            if sandbox.k8s_resource_version == cr_rv and new_status == sandbox.status:
                continue

            if new_status != sandbox.status and is_valid_transition(sandbox.status, new_status):
                old_status = sandbox.status
                rows = await _optimistic_update(
                    session, sandbox.id, sandbox.version, new_status, resource_version=cr_rv, message=message
                )
                if rows == 0:
                    logger.debug(
                        "Optimistic lock conflict for reconcile sandbox_id=%s (%s -> %s), skipping",
                        sandbox.id,
                        old_status,
                        new_status,
                    )
                else:
                    await _record_status_change(
                        session,
                        sandbox_id=sandbox.id,
                        from_status=old_status,
                        to_status=new_status,
                        source="k8s_reconcile",
                        message=message,
                    )
                    await _apply_metering_on_transition(session, sandbox, old_status, new_status)
                    await session.commit()
            elif cr_rv != sandbox.k8s_resource_version:
                await _update_sync_metadata(session, sandbox.id, cr_rv, message)

    # ── Metering reconciliation: fix mismatches between sessions/ledgers and sandbox state ──
    try:
        await reconcile_metering(session_factory)
    except Exception:
        logger.exception("Compute metering reconciliation failed")

    try:
        await reconcile_storage_metering(session_factory)
    except Exception:
        logger.exception("Storage metering reconciliation failed")

    # ── Template spec sync + validation: populate runtime cache and detect drift ──
    try:
        k8s_templates = await k8s_client.list_sandbox_templates(namespace)
        sync_template_specs_from_k8s(k8s_templates)
        validate_template_specs(k8s_templates)
    except Exception:
        logger.exception("Template spec sync/validation failed")

    logger.info("Reconciliation complete. %d unmanaged CRs in K8s. list_rv=%s", len(cr_map), list_rv)
    return list_rv


async def watch_loop(
    namespace: str,
    k8s_client: K8sClientProtocol,
    session_factory: async_sessionmaker[AsyncSession],
    resource_version: str,
) -> None:
    """Consume Watch events and update DB in real time. Raises WatchExpiredError on 410."""
    logger.debug("Watch loop starting from rv=%s", resource_version)
    async for event_type, cr_object in k8s_client.watch_sandboxes(namespace, resource_version):
        try:
            await handle_watch_event(event_type, cr_object, session_factory)
        except Exception:
            logger.exception("Error handling Watch event for %s", cr_object.get("metadata", {}).get("name"))
        rv = cr_object.get("metadata", {}).get("resourceVersion", "")
        if rv:
            resource_version = rv
    logger.debug("Watch stream ended (server closed connection)")


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
                logger.debug("Watch stream ended, restarting")
            except WatchExpiredError:
                logger.debug("Watch resourceVersion expired (410), re-listing")
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
    from treadstone.models.user import utc_now

    sandbox = await session.get(Sandbox, sandbox_id)
    if sandbox is None:
        return
    sandbox.status = SandboxStatus.DELETED
    sandbox.gmt_deleted = utc_now()
    session.add(sandbox)
    await session.commit()


async def _apply_metering_on_transition(
    session: AsyncSession,
    sandbox: Sandbox,
    old_status: str,
    new_status: str,
) -> None:
    """Open or close a ComputeSession based on sandbox state transition.

    Best-effort: failures are logged but never block the sync pipeline.
    reconcile_metering() will repair any missed operations.
    """
    try:
        if old_status != SandboxStatus.READY and new_status == SandboxStatus.READY:
            await _metering.open_compute_session(session, sandbox.id, sandbox.owner_id, sandbox.template)

        elif old_status == SandboxStatus.READY and new_status in (
            SandboxStatus.STOPPED,
            SandboxStatus.ERROR,
            SandboxStatus.DELETING,
        ):
            await _metering.close_compute_session(session, sandbox.id)
    except Exception:
        logger.exception("Metering transition failed for sandbox %s (%s→%s)", sandbox.id, old_status, new_status)


async def _try_close_compute_session(session: AsyncSession, sandbox_id: str) -> None:
    """Best-effort close of any open ComputeSession for the given sandbox."""
    try:
        await _metering.close_compute_session(session, sandbox_id)
    except Exception:
        logger.exception("Failed to close compute session for sandbox %s", sandbox_id)


async def _try_release_storage_ledger(session: AsyncSession, sandbox_id: str) -> None:
    """Best-effort release of ACTIVE StorageLedger for a persistent sandbox."""
    try:
        await _metering.record_storage_release(session, sandbox_id)
    except Exception:
        logger.exception("Failed to release storage ledger for sandbox %s", sandbox_id)


async def reconcile_metering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Check and repair mismatches between ComputeSession state and sandbox state.

    Two repair cases:
      1. sandbox is READY but has no open ComputeSession → open one
      2. sandbox is NOT READY (or missing) but has an open ComputeSession → close it
    """
    async with session_factory() as session:
        from treadstone.models.metering import ComputeSession

        # Case 1: READY sandboxes missing an open session (single JOIN query)
        missing_stmt = (
            select(Sandbox)
            .outerjoin(
                ComputeSession,
                and_(
                    ComputeSession.sandbox_id == Sandbox.id,
                    ComputeSession.ended_at.is_(None),
                ),
            )
            .where(
                Sandbox.status == SandboxStatus.READY,
                ComputeSession.id.is_(None),
            )
        )
        missing_result = await session.execute(missing_stmt)
        for sandbox in missing_result.scalars():
            logger.warning("Ready sandbox %s has no open ComputeSession, opening one", sandbox.id)
            try:
                await _metering.open_compute_session(session, sandbox.id, sandbox.owner_id, sandbox.template)
            except Exception:
                logger.exception("Failed to open compute session for sandbox %s during reconciliation", sandbox.id)

        # Case 2: open sessions for non-READY (or deleted) sandboxes (single JOIN query)
        stale_stmt = (
            select(ComputeSession, Sandbox)
            .outerjoin(Sandbox, ComputeSession.sandbox_id == Sandbox.id)
            .where(
                ComputeSession.ended_at.is_(None),
                or_(
                    Sandbox.id.is_(None),
                    Sandbox.status != SandboxStatus.READY,
                ),
            )
        )
        stale_result = await session.execute(stale_stmt)
        for cs, sandbox in stale_result:
            status_desc = sandbox.status if sandbox else "deleted"
            logger.warning(
                "ComputeSession %s for sandbox %s is open but sandbox is %s, closing",
                cs.id,
                cs.sandbox_id,
                status_desc,
            )
            try:
                await _metering.close_compute_session(session, cs.sandbox_id)
            except Exception:
                logger.exception(
                    "Failed to close compute session %s during reconciliation",
                    cs.id,
                )

        await session.commit()


async def reconcile_storage_metering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Check and repair mismatches between StorageLedger and persistent sandboxes.

    Two repair cases:
      1. persist sandbox (not DELETING) has no ACTIVE StorageLedger → create one
      2. ACTIVE StorageLedger whose sandbox is deleted/missing → release it
    """
    from treadstone.models.metering import StorageLedger, StorageState
    from treadstone.services.metering_helpers import parse_storage_size_gib

    async with session_factory() as session:
        # Case 1: persistent sandboxes missing a storage ledger entry (single JOIN query)
        missing_stmt = (
            select(Sandbox)
            .outerjoin(
                StorageLedger,
                and_(
                    StorageLedger.sandbox_id == Sandbox.id,
                    StorageLedger.storage_state == StorageState.ACTIVE,
                ),
            )
            .where(
                Sandbox.persist.is_(True),
                Sandbox.status.notin_([SandboxStatus.DELETING, SandboxStatus.DELETED]),
                Sandbox.storage_size.isnot(None),
                Sandbox.gmt_deleted.is_(None),
                StorageLedger.id.is_(None),
            )
        )
        missing_result = await session.execute(missing_stmt)
        for sandbox in missing_result.scalars():
            logger.warning("Persistent sandbox %s has no ACTIVE storage ledger, creating one", sandbox.id)
            try:
                size_gib = parse_storage_size_gib(sandbox.storage_size)
                await _metering.record_storage_allocation(session, sandbox.owner_id, sandbox.id, size_gib)
            except Exception:
                logger.exception("Failed to create storage ledger for sandbox %s during reconciliation", sandbox.id)

        # Case 2: ACTIVE ledger entries for deleted/missing sandboxes (single JOIN query)
        stale_stmt = (
            select(StorageLedger, Sandbox)
            .outerjoin(Sandbox, StorageLedger.sandbox_id == Sandbox.id)
            .where(
                StorageLedger.storage_state == StorageState.ACTIVE,
                or_(
                    StorageLedger.sandbox_id.is_(None),
                    Sandbox.id.is_(None),
                    Sandbox.status.in_([SandboxStatus.DELETING, SandboxStatus.DELETED]),
                ),
            )
        )
        stale_result = await session.execute(stale_stmt)
        for ledger, sandbox in stale_result:
            if ledger.sandbox_id is None:
                logger.warning(
                    "StorageLedger %s is ACTIVE but has NULL sandbox_id, skipping",
                    ledger.id,
                )
                continue
            status_desc = sandbox.status if sandbox else "deleted"
            logger.warning(
                "StorageLedger %s for sandbox %s is ACTIVE but sandbox is %s, releasing",
                ledger.id,
                ledger.sandbox_id,
                status_desc,
            )
            try:
                await _metering.record_storage_release(session, ledger.sandbox_id)
            except Exception:
                logger.exception(
                    "Failed to release storage ledger %s during reconciliation",
                    ledger.id,
                )

        await session.commit()


def _sandbox_status_log_value(to_status: str | SandboxStatus) -> str:
    return to_status.value if isinstance(to_status, SandboxStatus) else to_status


_LOGGED_SANDBOX_TRANSITIONS = frozenset({SandboxStatus.ERROR.value, SandboxStatus.DELETING.value, "deleted"})


async def _record_status_change(
    session: AsyncSession,
    *,
    sandbox_id: str,
    from_status: str,
    to_status: str | SandboxStatus,
    source: str,
    message: str | None = None,
) -> None:
    await record_audit_event(
        session,
        action="sandbox.status.change",
        target_type="sandbox",
        target_id=sandbox_id,
        actor_type=AuditActorType.SYSTEM.value,
        metadata={
            "from_status": from_status,
            "to_status": _sandbox_status_log_value(to_status),
            "source": source,
            "message": message,
        },
    )
    ts = _sandbox_status_log_value(to_status)
    if ts in _LOGGED_SANDBOX_TRANSITIONS:
        msg_suffix = f" message={message!r}" if message else ""
        logger.info("Sandbox %s status %s -> %s (source=%s)%s", sandbox_id, from_status, ts, source, msg_suffix)
