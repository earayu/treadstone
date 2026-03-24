import asyncio
from collections import deque

from treadstone.services.leader_election import LeadershipState
from treadstone.services.sync_supervisor import LeaderControlledSyncSupervisor


class FakeElector:
    def __init__(
        self,
        states: list[LeadershipState],
        *,
        renew_interval_seconds: float = 0.01,
        retry_interval_seconds: float = 0.01,
    ):
        self._states = deque(states)
        self._current = LeadershipState.FOLLOWER
        self.renew_interval_seconds = renew_interval_seconds
        self.retry_interval_seconds = retry_interval_seconds
        self.release_calls = 0

    async def try_acquire_or_renew(self) -> LeadershipState:
        if self._states:
            self._current = self._states.popleft()
        return self._current

    async def release_if_held(self) -> None:
        self.release_calls += 1


async def test_supervisor_starts_sync_when_leader_elected():
    elector = FakeElector([LeadershipState.LEADER])
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def sync_loop():
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    supervisor = LeaderControlledSyncSupervisor(elector=elector, sync_loop_factory=sync_loop)
    supervisor_task = asyncio.create_task(supervisor.run())

    await asyncio.wait_for(started.wait(), timeout=0.5)
    await supervisor.shutdown()
    supervisor_task.cancel()
    await asyncio.gather(supervisor_task, return_exceptions=True)

    assert cancelled.is_set()
    assert elector.release_calls == 1


async def test_supervisor_stops_sync_when_leadership_is_lost():
    elector = FakeElector([LeadershipState.LEADER, LeadershipState.FOLLOWER])
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def sync_loop():
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    supervisor = LeaderControlledSyncSupervisor(elector=elector, sync_loop_factory=sync_loop)
    supervisor_task = asyncio.create_task(supervisor.run())

    await asyncio.wait_for(started.wait(), timeout=0.5)
    await asyncio.wait_for(cancelled.wait(), timeout=0.5)
    await supervisor.shutdown()
    supervisor_task.cancel()
    await asyncio.gather(supervisor_task, return_exceptions=True)

    assert cancelled.is_set()
