"""Leader-aware wrapper around the K8s sync loop with metering tick integration."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.services.leader_election import LeadershipState

logger = logging.getLogger(__name__)


class LeaderControlledSyncSupervisor:
    """Start the sync loop only while this replica holds leadership.

    When a ``session_factory`` is provided, a metering tick loop runs
    alongside the sync loop for compute/storage metering, grace-period
    enforcement, and monthly resets — all bound to the leader lifecycle.
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

    async def run(self) -> None:
        try:
            while not self._stopping:
                self._reap_sync_task()
                self._reap_metering_task()
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
        from treadstone.services.metering_tasks import TICK_INTERVAL, run_metering_tick

        while True:
            await asyncio.sleep(TICK_INTERVAL)
            try:
                await run_metering_tick(self._session_factory)
            except Exception:
                logger.exception("Metering tick failed")

    async def _stop_all_tasks(self, reason: str) -> None:
        await self._stop_task(self._sync_task, "sync loop", reason)
        self._sync_task = None
        await self._stop_task(self._metering_task, "metering tick", reason)
        self._metering_task = None

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
