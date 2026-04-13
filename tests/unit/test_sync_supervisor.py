import asyncio
from collections import deque
from types import SimpleNamespace

import pytest

from treadstone.core.database import async_session
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


async def test_supervisor_metering_loop_runs_once_before_first_sleep(monkeypatch):
    calls: list[str] = []

    async def fake_run_metering_tick(session_factory, stop_sandbox_callback) -> None:
        assert session_factory is async_session
        assert stop_sandbox_callback is not None
        calls.append("run")

    async def fake_sleep(_seconds: int) -> None:
        calls.append("sleep")
        raise asyncio.CancelledError

    import treadstone.infra.services.sync_supervisor as sync_supervisor
    import treadstone.metering.services.metering_tasks as metering_tasks

    monkeypatch.setattr(metering_tasks, "run_metering_tick", fake_run_metering_tick)
    monkeypatch.setattr(sync_supervisor.asyncio, "sleep", fake_sleep)

    supervisor = LeaderControlledSyncSupervisor(
        elector=SimpleNamespace(),
        sync_loop_factory=lambda: asyncio.sleep(0),
        session_factory=async_session,
    )

    with pytest.raises(asyncio.CancelledError):
        await supervisor._metering_tick_loop()

    assert calls == ["run", "sleep"]


async def test_supervisor_lifecycle_loop_runs_once_before_first_sleep(monkeypatch):
    calls: list[str] = []

    async def fake_run_lifecycle_tick(session_factory, stop_sandbox_callback, delete_sandbox_callback) -> None:
        assert session_factory is async_session
        assert stop_sandbox_callback is not None
        assert delete_sandbox_callback is not None
        calls.append("run")

    async def fake_sleep(_seconds: int) -> None:
        calls.append("sleep")
        raise asyncio.CancelledError

    import treadstone.infra.services.sandbox_lifecycle_tasks as lifecycle_tasks
    import treadstone.infra.services.sync_supervisor as sync_supervisor

    monkeypatch.setattr(lifecycle_tasks, "run_lifecycle_tick", fake_run_lifecycle_tick)
    monkeypatch.setattr(sync_supervisor.asyncio, "sleep", fake_sleep)

    supervisor = LeaderControlledSyncSupervisor(
        elector=SimpleNamespace(),
        sync_loop_factory=lambda: asyncio.sleep(0),
        session_factory=async_session,
    )

    with pytest.raises(asyncio.CancelledError):
        await supervisor._lifecycle_tick_loop()

    assert calls == ["run", "sleep"]
