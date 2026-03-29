"""Unit tests for sandbox lifecycle tasks — idle auto-stop and auto-delete."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.services.sandbox_lifecycle_tasks import (
    check_auto_delete,
    check_idle_auto_stop,
    run_lifecycle_tick,
)

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


def _make_sandbox(**overrides) -> Sandbox:
    defaults = {
        "id": "sb_test_lifecycle_01",
        "name": "test-sandbox",
        "owner_id": "user_test_01",
        "template": "aio-sandbox-small",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.READY,
        "version": 1,
        "endpoints": {},
        "k8s_sandbox_claim_name": "sb_test_lifecycle_01",
        "k8s_sandbox_name": "sb_test_lifecycle_01",
        "k8s_namespace": "treadstone-local",
        "persist": False,
        "storage_size": None,
        "provision_mode": "claim",
        "gmt_last_active": FIXED_NOW - timedelta(minutes=20),
        "gmt_stopped": None,
    }
    defaults.update(overrides)
    sb = Sandbox()
    for k, v in defaults.items():
        setattr(sb, k, v)
    return sb


def _mock_session_with_sandboxes(sandboxes: list[Sandbox]) -> AsyncMock:
    """Build a mock AsyncSession that returns sandboxes from execute()."""
    session = AsyncMock()

    class _MockScalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _MockResult:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return _MockScalars(self._items)

    session.execute.return_value = _MockResult(sandboxes)
    return session


# ═══════════════════════════════════════════════════
#  check_idle_auto_stop
# ═══════════════════════════════════════════════════


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks._metering", create=True)
async def test_idle_auto_stop_stops_idle_sandbox(mock_metering, mock_audit, mock_now):
    """Sandbox idle > auto_stop_interval should be stopped with eager DB state update."""
    mock_metering.close_compute_session = AsyncMock()
    sandbox = _make_sandbox(
        auto_stop_interval=15,
        gmt_last_active=FIXED_NOW - timedelta(minutes=20),
        status=SandboxStatus.READY,
    )
    session = _mock_session_with_sandboxes([sandbox])
    stop_cb = AsyncMock()

    await check_idle_auto_stop(session, stop_callback=stop_cb)

    stop_cb.assert_called_once_with(session, sandbox)
    # Eager DB update prevents re-triggering on next tick
    assert sandbox.status == SandboxStatus.STOPPED
    assert sandbox.gmt_stopped == FIXED_NOW
    mock_metering.close_compute_session.assert_called_once_with(session, sandbox.id)
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "sandbox.idle_auto_stop"
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks._metering", create=True)
async def test_idle_auto_stop_skips_active_sandbox(mock_metering, mock_audit, mock_now):
    """Sandbox idle < auto_stop_interval should NOT be stopped."""
    mock_metering.close_compute_session = AsyncMock()
    sandbox = _make_sandbox(
        auto_stop_interval=15,
        gmt_last_active=FIXED_NOW - timedelta(minutes=5),
    )
    session = _mock_session_with_sandboxes([sandbox])
    stop_cb = AsyncMock()

    await check_idle_auto_stop(session, stop_callback=stop_cb)

    stop_cb.assert_not_called()
    mock_metering.close_compute_session.assert_not_called()
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks._metering", create=True)
async def test_idle_auto_stop_callback_failure_does_not_block_others(mock_metering, mock_audit, mock_now):
    """Failure stopping one sandbox should not prevent stopping another."""
    mock_metering.close_compute_session = AsyncMock()
    sb1 = _make_sandbox(id="sb_fail", gmt_last_active=FIXED_NOW - timedelta(minutes=20))
    sb2 = _make_sandbox(id="sb_ok", gmt_last_active=FIXED_NOW - timedelta(minutes=20))
    session = _mock_session_with_sandboxes([sb1, sb2])

    stop_cb = AsyncMock(side_effect=[RuntimeError("K8s timeout"), None])

    await check_idle_auto_stop(session, stop_callback=stop_cb)

    assert stop_cb.call_count == 2
    mock_metering.close_compute_session.assert_called_once_with(session, "sb_ok")
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks._metering", create=True)
async def test_idle_auto_stop_uses_db_fallback_without_callback(mock_metering, mock_audit, mock_now):
    """Without a stop callback, should fall back to _db_only_stop."""
    mock_metering.close_compute_session = AsyncMock()
    sandbox = _make_sandbox(gmt_last_active=FIXED_NOW - timedelta(minutes=20))
    session = _mock_session_with_sandboxes([sandbox])

    await check_idle_auto_stop(session, stop_callback=None)

    assert sandbox.status == SandboxStatus.STOPPED
    assert sandbox.gmt_stopped is not None
    session.commit.assert_called_once()


# ═══════════════════════════════════════════════════
#  check_auto_delete
# ═══════════════════════════════════════════════════


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_deletes_expired_sandbox(mock_audit, mock_now):
    """Stopped sandbox past auto_delete_interval should be deleted."""
    sandbox = _make_sandbox(
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=FIXED_NOW - timedelta(minutes=90),
    )
    session = _mock_session_with_sandboxes([sandbox])
    delete_cb = AsyncMock()

    await check_auto_delete(session, delete_callback=delete_cb)

    delete_cb.assert_called_once_with(session, sandbox)
    mock_audit.assert_called_once()
    assert mock_audit.call_args.kwargs["action"] == "sandbox.auto_delete"
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_skips_recently_stopped_sandbox(mock_audit, mock_now):
    """Stopped sandbox within auto_delete_interval should NOT be deleted."""
    sandbox = _make_sandbox(
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=FIXED_NOW - timedelta(minutes=30),
    )
    session = _mock_session_with_sandboxes([sandbox])
    delete_cb = AsyncMock()

    await check_auto_delete(session, delete_callback=delete_cb)

    delete_cb.assert_not_called()
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_callback_failure_does_not_block_others(mock_audit, mock_now):
    """Failure deleting one sandbox should not prevent deleting another."""
    sb1 = _make_sandbox(
        id="sb_fail",
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=FIXED_NOW - timedelta(minutes=90),
    )
    sb2 = _make_sandbox(
        id="sb_ok",
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=FIXED_NOW - timedelta(minutes=90),
    )
    session = _mock_session_with_sandboxes([sb1, sb2])
    delete_cb = AsyncMock(side_effect=[RuntimeError("K8s timeout"), None])

    await check_auto_delete(session, delete_callback=delete_cb)

    assert delete_cb.call_count == 2
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_uses_db_fallback_without_callback(mock_audit, mock_now):
    """Without a delete callback, should fall back to _db_only_delete."""
    sandbox = _make_sandbox(
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=FIXED_NOW - timedelta(minutes=90),
    )
    session = _mock_session_with_sandboxes([sandbox])

    await check_auto_delete(session, delete_callback=None)

    assert sandbox.status == SandboxStatus.DELETING
    assert sandbox.gmt_deleted is not None
    session.commit.assert_called_once()


# ═══════════════════════════════════════════════════
#  run_lifecycle_tick
# ═══════════════════════════════════════════════════


@patch("treadstone.services.sandbox_lifecycle_tasks.check_auto_delete", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks.check_idle_auto_stop", new_callable=AsyncMock)
async def test_run_lifecycle_tick_calls_both_steps(mock_idle, mock_delete):
    """run_lifecycle_tick should execute both sub-steps with independent sessions."""
    factory = AsyncMock()
    session_a, session_b = AsyncMock(), AsyncMock()
    factory.return_value.__aenter__ = AsyncMock(side_effect=[session_a, session_b])
    factory.return_value.__aexit__ = AsyncMock(return_value=False)

    stop_cb = AsyncMock()
    delete_cb = AsyncMock()

    await run_lifecycle_tick(factory, stop_sandbox_callback=stop_cb, delete_sandbox_callback=delete_cb)

    assert factory.call_count == 2


@patch("treadstone.services.sandbox_lifecycle_tasks.check_auto_delete", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks.check_idle_auto_stop", new_callable=AsyncMock)
async def test_run_lifecycle_tick_step_failure_does_not_block_next(mock_idle, mock_delete):
    """If check_idle_auto_stop fails, check_auto_delete should still run."""
    factory = AsyncMock()
    mock_idle.side_effect = RuntimeError("DB error")

    await run_lifecycle_tick(factory)

    assert factory.call_count == 2
