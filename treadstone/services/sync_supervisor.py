"""Leader-aware wrapper around the K8s sync loop."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from treadstone.services.leader_election import LeadershipState

logger = logging.getLogger(__name__)


class LeaderControlledSyncSupervisor:
    """Start the sync loop only while this replica holds leadership."""

    def __init__(self, *, elector, sync_loop_factory: Callable[[], Awaitable[None]]) -> None:
        self._elector = elector
        self._sync_loop_factory = sync_loop_factory
        self._stopping = False
        self._shutdown_complete = False
        self._shutdown_lock = asyncio.Lock()
        self._sync_task: asyncio.Task | None = None

    async def run(self) -> None:
        try:
            while not self._stopping:
                self._reap_sync_task()
                try:
                    state = await self._elector.try_acquire_or_renew()
                except Exception:
                    logger.exception("Leader election loop failed")
                    await self._stop_sync_task("leader election error")
                    state = LeadershipState.FOLLOWER

                if state == LeadershipState.LEADER:
                    if self._sync_task is None:
                        self._sync_task = asyncio.create_task(self._sync_loop_factory())
                        logger.info("Leadership held; started K8s sync loop")
                    await asyncio.sleep(self._elector.renew_interval_seconds)
                else:
                    await self._stop_sync_task("leadership lost")
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
            await self._stop_sync_task("shutdown")
            try:
                await self._elector.release_if_held()
            except Exception:
                logger.exception("Failed to release leadership during shutdown")
            self._shutdown_complete = True

    async def _stop_sync_task(self, reason: str) -> None:
        if self._sync_task is None:
            return
        task = self._sync_task
        self._sync_task = None

        if not task.done():
            logger.info("Stopping K8s sync loop (%s)", reason)
            task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    def _reap_sync_task(self) -> None:
        if self._sync_task is None or not self._sync_task.done():
            return

        task = self._sync_task
        self._sync_task = None
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("K8s sync loop exited unexpectedly", exc_info=(type(exc), exc, exc.__traceback__))
