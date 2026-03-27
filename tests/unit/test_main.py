import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import treadstone.main as main
from treadstone.core.database import async_session


async def test_lifespan_passes_session_factory_to_supervisor_when_leader_election_enabled(monkeypatch):
    close_http_client = AsyncMock()
    captured: dict[str, object] = {}
    run_started = asyncio.Event()
    task_cancelled = asyncio.Event()

    class CapturingSupervisor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        async def run(self) -> None:
            run_started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                task_cancelled.set()
                raise

        async def shutdown(self) -> None:
            captured["shutdown_called"] = True

    monkeypatch.setattr(main.settings, "leader_election_enabled", True)
    monkeypatch.setattr(main.settings, "pod_name", "test-pod")
    monkeypatch.setattr(main.settings, "pod_namespace", "test-namespace")

    import treadstone.services.leader_election as leader_election
    import treadstone.services.sync_supervisor as sync_supervisor

    monkeypatch.setattr(leader_election, "K8sLeaseStore", lambda: object())
    monkeypatch.setattr(
        leader_election,
        "LeaderElector",
        lambda **kwargs: SimpleNamespace(
            renew_interval_seconds=kwargs["renew_interval_seconds"],
            retry_interval_seconds=kwargs["retry_interval_seconds"],
            release_if_held=AsyncMock(),
        ),
    )
    monkeypatch.setattr(sync_supervisor, "LeaderControlledSyncSupervisor", CapturingSupervisor)
    monkeypatch.setattr(main, "close_http_client", close_http_client)

    async with main.lifespan(main.app):
        assert captured["session_factory"] is async_session
        await asyncio.wait_for(run_started.wait(), timeout=0.5)

    assert captured["shutdown_called"] is True
    assert task_cancelled.is_set()
    close_http_client.assert_awaited_once()


async def test_lifespan_starts_metering_loop_when_leader_election_disabled(monkeypatch):
    sync_started = asyncio.Event()
    sync_cancelled = asyncio.Event()
    metering_started = asyncio.Event()
    metering_cancelled = asyncio.Event()
    close_http_client = AsyncMock()

    async def fake_sync_loop(*_args) -> None:
        sync_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            sync_cancelled.set()
            raise

    async def fake_metering_loop(_session_factory) -> None:
        metering_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            metering_cancelled.set()
            raise

    monkeypatch.setattr(main.settings, "leader_election_enabled", False)
    monkeypatch.setattr(main, "_run_metering_loop", fake_metering_loop)

    import treadstone.services.k8s_client as k8s_client
    import treadstone.services.k8s_sync as k8s_sync

    monkeypatch.setattr(k8s_client, "get_k8s_client", lambda: object())
    monkeypatch.setattr(k8s_sync, "start_sync_loop", fake_sync_loop)
    monkeypatch.setattr(main, "close_http_client", close_http_client)

    async with main.lifespan(main.app):
        await asyncio.wait_for(sync_started.wait(), timeout=0.5)
        await asyncio.wait_for(metering_started.wait(), timeout=0.5)

    assert sync_cancelled.is_set()
    assert metering_cancelled.is_set()
    close_http_client.assert_awaited_once()
