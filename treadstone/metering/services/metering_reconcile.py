"""Metering reconciliation hooks — repair drift between ComputeSession/StorageLedger and sandbox state.

These functions are registered as ReconcileHooks and called by the k8s_sync
reconcile loop.  They were previously inlined in k8s_sync.py; moving them here
keeps the infra module independent of the metering module.
"""

import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.metering.models.metering import ComputeSession, StorageLedger, StorageState
from treadstone.metering.services.metering_helpers import (
    parse_storage_size_gib,
    sync_template_specs_from_k8s,
    validate_template_specs,
)
from treadstone.metering.services.metering_service import MeteringService
from treadstone.sandbox.models.sandbox import Sandbox, SandboxStatus

logger = logging.getLogger(__name__)

__all__ = [
    "reconcile_metering",
    "reconcile_storage_metering",
    "reconcile_template_specs",
]


async def reconcile_metering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Check and repair mismatches between ComputeSession state and sandbox state.

    Two repair cases:
      1. sandbox is READY but has no open ComputeSession -> open one
      2. sandbox is NOT READY (or missing) but has an open ComputeSession -> close it
    """
    metering = MeteringService()

    async with session_factory() as session:
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
                await metering.open_compute_session(session, sandbox.id, sandbox.owner_id, sandbox.template)
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
                await metering.close_compute_session(session, cs.sandbox_id)
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
      1. persist sandbox (not DELETING) has no ACTIVE StorageLedger -> create one
      2. ACTIVE StorageLedger whose sandbox is deleted/missing -> release it
    """
    metering = MeteringService()

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
                await metering.record_storage_allocation(
                    session,
                    sandbox.owner_id,
                    sandbox.id,
                    size_gib,
                    backend_mode=sandbox.storage_backend_mode or "live_disk",
                )
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
                await metering.record_storage_release(session, ledger.sandbox_id)
            except Exception:
                logger.exception(
                    "Failed to release storage ledger %s during reconciliation",
                    ledger.id,
                )

        await session.commit()


async def reconcile_template_specs(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    k8s_client=None,
    namespace: str | None = None,
) -> None:
    """Sync template specs from K8s and validate against static TEMPLATE_SPECS.

    This is called as a reconcile hook.  The k8s_client and namespace are bound
    at registration time via a partial/closure.
    """
    if k8s_client is None:
        return
    try:
        k8s_templates = await k8s_client.list_sandbox_templates(namespace)
        sync_template_specs_from_k8s(k8s_templates)
        validate_template_specs(k8s_templates)
    except Exception:
        logger.exception("Template spec sync/validation failed")
