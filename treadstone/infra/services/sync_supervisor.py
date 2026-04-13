"""Leader-aware wrapper around the K8s sync loop with metering and lifecycle tick integration."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.identity.models.user import utc_now
from treadstone.infra.services.leader_election import LeadershipState
from treadstone.sandbox.models.sandbox import SandboxStatus

logger = logging.getLogger(__name__)


async def _k8s_stop_sandbox(session, sandbox) -> None:
    """Stop a sandbox via K8s scale-down (used as grace-period enforcement callback).

    Exceptions propagate to the caller (_enforce_stop) so it can accurately
    track which sandbox stops failed and preserve grace state accordingly.
    """
    from treadstone.infra.services.k8s_client import get_k8s_client

    k8s = get_k8s_client()
    k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
    await k8s.scale_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace, replicas=0)


async def _k8s_delete_sandbox(session, sandbox) -> None:
    """Delete a sandbox K8s resource (used as auto-delete callback).

    Soft-deletes the SandboxWebLink, marks sandbox as DELETING in DB, then
    calls the K8s API.  ``gmt_deleted`` stays unset until watch/reconcile
    confirms the CR is gone, otherwise sync queries would stop seeing the row
    before they can finalize it to DELETED. If K8s fails, rolls back the
    in-memory state and re-raises so the outer handler does NOT commit a
    broken DELETING status.
    The watch/reconcile loop transitions to DELETED once the CR is gone.

    COLD sandboxes have no running K8s compute resources — only VolumeSnapshot
    assets.  For these we clean up snapshot resources and finalize immediately
    to DELETED since there is no CR for watch/reconcile to observe.
    """
    from sqlalchemy import select

    from treadstone.infra.services.k8s_client import get_k8s_client
    from treadstone.sandbox.models.sandbox import StorageBackendMode
    from treadstone.sandbox.models.sandbox_web_link import SandboxWebLink

    link_result = await session.execute(
        select(SandboxWebLink).where(
            SandboxWebLink.sandbox_id == sandbox.id,
            SandboxWebLink.gmt_deleted.is_(None),
        )
    )
    link = link_result.scalar_one_or_none()
    if link is not None:
        link.gmt_deleted = utc_now()
        link.gmt_updated = utc_now()
        session.add(link)

    if sandbox.status == SandboxStatus.COLD or sandbox.storage_backend_mode == StorageBackendMode.STANDARD_SNAPSHOT:
        from treadstone.infra.services.sandbox_lifecycle_tasks import AutoDeleteFailure
        from treadstone.metering.services.metering_service import MeteringService
        from treadstone.storage.services.storage_snapshot_orchestrator import StorageSnapshotOrchestrator

        k8s = get_k8s_client()
        storage = StorageSnapshotOrchestrator(session=session, k8s_client=k8s)
        try:
            await storage.backend.delete_bound_snapshot(sandbox)
            storage._clear_snapshot_binding(sandbox)
        except Exception as exc:
            logger.exception("Failed to clean up snapshot for cold sandbox %s during auto-delete", sandbox.id)
            raise AutoDeleteFailure("Auto-delete failed: could not clean up cold snapshot asset") from exc
        try:
            metering = MeteringService()
            await metering.record_storage_release(session, sandbox.id)
        except Exception as exc:
            logger.exception("Failed to release storage ledger for cold sandbox %s during auto-delete", sandbox.id)
            raise AutoDeleteFailure(
                "Auto-delete failed: could not release storage ledger",
                clear_snapshot_binding=True,
            ) from exc
        sandbox.status = SandboxStatus.DELETED
        sandbox.gmt_deleted = utc_now()
        sandbox.version += 1
        session.add(sandbox)
        logger.info(
            "Sandbox %s status cold -> deleted (source=lifecycle_auto_delete)",
            sandbox.id,
        )
        return

    prev_status = sandbox.status
    sandbox.status = SandboxStatus.DELETING
    sandbox.version += 1
    session.add(sandbox)

    k8s = get_k8s_client()
    try:
        if sandbox.provision_mode == "direct":
            name = sandbox.k8s_sandbox_name or sandbox.id
            await k8s.delete_sandbox(name=name, namespace=sandbox.k8s_namespace)
        else:
            name = sandbox.k8s_sandbox_claim_name or sandbox.id
            await k8s.delete_sandbox_claim(name=name, namespace=sandbox.k8s_namespace)
        logger.info(
            "Sandbox %s status %s -> deleting (source=lifecycle_auto_delete)",
            sandbox.id,
            prev_status,
        )
    except Exception:
        sandbox.status = SandboxStatus.STOPPED
        sandbox.version -= 1
        session.add(sandbox)
        if link is not None:
            link.gmt_deleted = None
            link.gmt_updated = utc_now()
            session.add(link)
        raise


class LeaderControlledSyncSupervisor:
    """Start the sync loop only while this replica holds leadership.

    When a ``session_factory`` is provided, metering and lifecycle tick loops
    run alongside the sync loop — all bound to the leader lifecycle.
    """

    def __init__(
        self,
        *,
        elector,
        sync_loop_factory: Callable[[], Awaitable[None]],
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._elector = elector
        self._sync_loop_factory = sync_loop_factory
        self._session_factory = session_factory
        self._stopping = False
        self._shutdown_complete = False
        self._shutdown_lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None
        self._metering_task: asyncio.Task | None = None
        self._lifecycle_task: asyncio.Task | None = None
        self._snapshot_task: asyncio.Task | None = None

    async def run(self) -> None:
        try:
            while not self._stopping:
                self._reap_sync_task()
                self._reap_metering_task()
                self._reap_lifecycle_task()
                self._reap_snapshot_task()
                try:
                    state = await self._elector.try_acquire_or_renew()
                except Exception:
                    logger.exception("Leader election loop failed")
                    await self._stop_all_tasks("leader election error")
                    state = LeadershipState.FOLLOWER

                if state == LeadershipState.LEADER:
                    if self._sync_task is None:
                        self._sync_task = asyncio.create_task(self._sync_loop_factory())
                        logger.info("Leadership held; started K8s sync loop")
                    if self._metering_task is None and self._session_factory is not None:
                        self._metering_task = asyncio.create_task(self._metering_tick_loop())
                        logger.info("Started metering tick loop")
                    if self._lifecycle_task is None and self._session_factory is not None:
                        self._lifecycle_task = asyncio.create_task(self._lifecycle_tick_loop())
                        logger.info("Started lifecycle tick loop")
                    if self._snapshot_task is None and self._session_factory is not None:
                        self._snapshot_task = asyncio.create_task(self._snapshot_tick_loop())
                        logger.info("Started storage snapshot tick loop")
                    await asyncio.sleep(self._elector.renew_interval_seconds)
                else:
                    await self._stop_all_tasks("leadership lost")
                    await asyncio.sleep(self._elector.retry_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Sync supervisor shutting down")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        if self._shutdown_complete:
            return

        async with self._shutdown_lock:
            if self._shutdown_complete:
                return

            self._stopping = True
            await self._stop_all_tasks("shutdown")
            try:
                await self._elector.release_if_held()
            except Exception:
                logger.exception("Failed to release leadership during shutdown")
            self._shutdown_complete = True

    async def _metering_tick_loop(self) -> None:
        """Periodic metering tick — runs only while this instance is leader."""
        from treadstone.metering.services.metering_tasks import TICK_INTERVAL, run_metering_tick

        while True:
            try:
                await run_metering_tick(self._session_factory, stop_sandbox_callback=_k8s_stop_sandbox)
            except Exception:
                logger.exception("Metering tick failed")
            await asyncio.sleep(TICK_INTERVAL)

    async def _lifecycle_tick_loop(self) -> None:
        """Periodic lifecycle tick — idle auto-stop and auto-delete."""
        from treadstone.infra.services.sandbox_lifecycle_tasks import LIFECYCLE_TICK_INTERVAL, run_lifecycle_tick

        while True:
            try:
                await run_lifecycle_tick(
                    self._session_factory,
                    stop_sandbox_callback=_k8s_stop_sandbox,
                    delete_sandbox_callback=_k8s_delete_sandbox,
                )
            except Exception:
                logger.exception("Lifecycle tick failed")
            await asyncio.sleep(LIFECYCLE_TICK_INTERVAL)

    async def _snapshot_tick_loop(self) -> None:
        from treadstone.storage.services.storage_snapshot_orchestrator import (
            SNAPSHOT_TICK_INTERVAL,
            run_storage_snapshot_tick,
        )

        while True:
            try:
                await run_storage_snapshot_tick(self._session_factory)
            except Exception:
                logger.exception("Storage snapshot tick failed")
            await asyncio.sleep(SNAPSHOT_TICK_INTERVAL)

    async def _stop_all_tasks(self, reason: str) -> None:
        await self._stop_task(self._sync_task, "sync loop", reason)
        self._sync_task = None
        await self._stop_task(self._metering_task, "metering tick", reason)
        self._metering_task = None
        await self._stop_task(self._lifecycle_task, "lifecycle tick", reason)
        self._lifecycle_task = None
        await self._stop_task(self._snapshot_task, "storage snapshot tick", reason)
        self._snapshot_task = None

    @staticmethod
    async def _stop_task(task: asyncio.Task | None, name: str, reason: str) -> None:
        if task is None:
            return
        if not task.done():
            logger.info("Stopping %s (%s)", name, reason)
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _reap_sync_task(self) -> None:
        self._sync_task = self._reap_task(self._sync_task, "K8s sync loop")

    def _reap_metering_task(self) -> None:
        self._metering_task = self._reap_task(self._metering_task, "metering tick loop")

    def _reap_lifecycle_task(self) -> None:
        self._lifecycle_task = self._reap_task(self._lifecycle_task, "lifecycle tick loop")

    def _reap_snapshot_task(self) -> None:
        self._snapshot_task = self._reap_task(self._snapshot_task, "storage snapshot tick loop")

    @staticmethod
    def _reap_task(task: asyncio.Task | None, name: str) -> asyncio.Task | None:
        if task is None or not task.done():
            return task
        if task.cancelled():
            return None
        exc = task.exception()
        if exc is not None:
            logger.error("%s exited unexpectedly", name, exc_info=(type(exc), exc, exc.__traceback__))
        return None
