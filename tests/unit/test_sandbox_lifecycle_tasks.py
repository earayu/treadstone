"""Unit tests for sandbox lifecycle tasks — idle auto-stop and auto-delete."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import User
from treadstone.services.k8s_sync import handle_watch_event
from treadstone.services.sandbox_lifecycle_tasks import (
    check_auto_delete,
    check_idle_auto_stop,
    run_lifecycle_tick,
)
from treadstone.services.sync_supervisor import _k8s_delete_sandbox

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
REAL_FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0)


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
    session.add = Mock()

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
    nested_cm = AsyncMock()
    nested_cm.__aenter__ = AsyncMock(return_value=session)
    nested_cm.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = Mock(return_value=nested_cm)
    return session


def _async_context_manager(value):
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        user = User(id="user_test_01", email="test@example.com", hashed_password="x", role="admin")
        session.add(user)
        await session.commit()

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _insert_real_sandbox(factory, **overrides) -> str:
    sandbox = _make_sandbox(**overrides)
    async with factory() as session:
        session.add(sandbox)
        await session.commit()
    return sandbox.id


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
    assert sandbox.gmt_deleted is None
    session.commit.assert_called_once()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=REAL_FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks._metering", create=True)
async def test_idle_auto_stop_rolls_back_partial_db_update_on_followup_failure(
    mock_metering,
    mock_audit,
    mock_now,
    session_factory,
):
    """A failed follow-up step must not commit the eager STOPPED state."""
    mock_metering.close_compute_session = AsyncMock(side_effect=RuntimeError("metering unavailable"))
    sandbox_id = await _insert_real_sandbox(
        session_factory,
        id="sb_real_idle_01",
        status=SandboxStatus.READY,
        auto_stop_interval=15,
        gmt_last_active=REAL_FIXED_NOW - timedelta(minutes=20),
    )

    async with session_factory() as session:
        await check_idle_auto_stop(session, stop_callback=None)

    async with session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.READY
        assert sandbox.gmt_stopped is None
        assert sandbox.version == 1
    mock_audit.assert_not_called()


@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=REAL_FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_rolls_back_partial_delete_on_audit_failure(mock_audit, mock_now, session_factory):
    """A failed audit write must not leave the sandbox stuck in DELETING."""
    mock_audit.side_effect = RuntimeError("audit table unavailable")
    sandbox_id = await _insert_real_sandbox(
        session_factory,
        id="sb_real_delete_01",
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=REAL_FIXED_NOW - timedelta(minutes=90),
    )

    async with session_factory() as session:
        await check_auto_delete(session, delete_callback=None)

    async with session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.STOPPED
        assert sandbox.gmt_deleted is None
        assert sandbox.version == 1


@patch("treadstone.services.sync_supervisor.utc_now", return_value=REAL_FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.utc_now", return_value=REAL_FIXED_NOW)
@patch("treadstone.services.sandbox_lifecycle_tasks.record_audit_event", new_callable=AsyncMock)
async def test_auto_delete_k8s_path_stays_trackable_until_watch_finishes(
    mock_audit,
    mock_lifecycle_now,
    mock_supervisor_now,
    session_factory,
):
    """Lifecycle auto-delete must keep the row visible to watch/reconcile until finalization."""
    sandbox_id = await _insert_real_sandbox(
        session_factory,
        id="sb_real_delete_02",
        name="real-delete",
        status=SandboxStatus.STOPPED,
        auto_delete_interval=60,
        gmt_stopped=REAL_FIXED_NOW - timedelta(minutes=90),
        k8s_sandbox_claim_name="real-delete",
        k8s_sandbox_name="real-delete",
    )
    async with session_factory() as session:
        session.add(
            SandboxWebLink(
                id="link_test_01",
                sandbox_id=sandbox_id,
                created_by_user_id="user_test_01",
                gmt_expires=None,
            )
        )
        await session.commit()

    async with session_factory() as session:
        await check_auto_delete(session, delete_callback=_k8s_delete_sandbox)

    async with session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        link = (
            await session.execute(select(SandboxWebLink).where(SandboxWebLink.sandbox_id == sandbox_id))
        ).scalar_one()
        assert sandbox.status == SandboxStatus.DELETING
        assert sandbox.gmt_deleted is None
        assert link.gmt_deleted == REAL_FIXED_NOW

    deleted_cr = {"metadata": {"name": "real-delete", "namespace": "treadstone-local", "resourceVersion": "99"}}
    await handle_watch_event("DELETED", deleted_cr, session_factory)

    async with session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.DELETED
        assert sandbox.gmt_deleted is not None


# ═══════════════════════════════════════════════════
#  run_lifecycle_tick
# ═══════════════════════════════════════════════════


@patch("treadstone.services.sandbox_lifecycle_tasks.check_auto_delete", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks.check_idle_auto_stop", new_callable=AsyncMock)
async def test_run_lifecycle_tick_calls_both_steps(mock_idle, mock_delete):
    """run_lifecycle_tick should execute both sub-steps with independent sessions."""
    factory = Mock()
    session_a, session_b = AsyncMock(), AsyncMock()
    factory.side_effect = [_async_context_manager(session_a), _async_context_manager(session_b)]

    stop_cb = AsyncMock()
    delete_cb = AsyncMock()

    await run_lifecycle_tick(factory, stop_sandbox_callback=stop_cb, delete_sandbox_callback=delete_cb)

    assert factory.call_count == 2


@patch("treadstone.services.sandbox_lifecycle_tasks.check_auto_delete", new_callable=AsyncMock)
@patch("treadstone.services.sandbox_lifecycle_tasks.check_idle_auto_stop", new_callable=AsyncMock)
async def test_run_lifecycle_tick_step_failure_does_not_block_next(mock_idle, mock_delete):
    """If check_idle_auto_stop fails, check_auto_delete should still run."""
    factory = Mock()
    factory.side_effect = [_async_context_manager(AsyncMock()), _async_context_manager(AsyncMock())]
    mock_idle.side_effect = RuntimeError("DB error")

    await run_lifecycle_tick(factory)

    assert factory.call_count == 2
