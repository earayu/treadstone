"""Unit tests for metering background tasks (Layer 4: F18–F23)."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from treadstone.models.metering import ComputeSession, StorageLedger, StorageState, UserPlan
from treadstone.models.sandbox import Sandbox, SandboxStatus

# ── Helpers ──────────────────────────────────────────────

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
ONE_MINUTE_AGO = FIXED_NOW - timedelta(seconds=60)
FIVE_MINUTES_AGO = FIXED_NOW - timedelta(minutes=5)


def _make_open_session(
    session_id: str = "cs_test01",
    sandbox_id: str = "sb_test01",
    user_id: str = "user_01",
    template: str = "aio-sandbox-small",
    vcpu_request: Decimal | None = None,
    memory_gib_request: Decimal | None = None,
    last_metered_at: datetime = ONE_MINUTE_AGO,
    gmt_updated: datetime = ONE_MINUTE_AGO,
    vcpu_hours: Decimal = Decimal("0"),
    memory_gib_hours: Decimal = Decimal("0"),
) -> ComputeSession:
    if vcpu_request is None:
        vcpu_request = Decimal("1") if template == "aio-sandbox-medium" else Decimal("0.5")
    if memory_gib_request is None:
        memory_gib_request = Decimal("2") if template == "aio-sandbox-medium" else Decimal("1")
    return ComputeSession(
        id=session_id,
        sandbox_id=sandbox_id,
        user_id=user_id,
        template=template,
        vcpu_request=vcpu_request,
        memory_gib_request=memory_gib_request,
        started_at=FIXED_NOW - timedelta(hours=1),
        last_metered_at=last_metered_at,
        vcpu_hours=vcpu_hours,
        memory_gib_hours=memory_gib_hours,
        gmt_updated=gmt_updated,
    )


def _assert_tick_update_resource_hours(
    stmt,
    *,
    expected_delta_vcpu: Decimal,
    expected_delta_mem: Decimal,
) -> None:
    """tick_metering issues UPDATE compute_session with incremental vcpu_hours / memory_gib_hours."""
    sql_text = str(stmt).lower()
    assert "vcpu_hours" in sql_text
    assert "memory_gib_hours" in sql_text
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql_literal = str(compiled).lower()
    m_vcpu = re.search(r"compute_session\.vcpu_hours \+ ([0-9.]+)", sql_literal)
    m_mem = re.search(r"compute_session\.memory_gib_hours \+ ([0-9.]+)", sql_literal)
    assert m_vcpu and m_mem, sql_literal
    got_vcpu = Decimal(m_vcpu.group(1))
    got_mem = Decimal(m_mem.group(1))
    assert abs(got_vcpu - expected_delta_vcpu) < Decimal("1e-15")
    assert abs(got_mem - expected_delta_mem) < Decimal("1e-15")


def _make_storage_entry(
    entry_id: str = "sl_test01",
    user_id: str = "user_01",
    sandbox_id: str = "sb_test01",
    size_gib: int = 10,
    last_metered_at: datetime = ONE_MINUTE_AGO,
    gib_hours: Decimal = Decimal("0"),
) -> StorageLedger:
    return StorageLedger(
        id=entry_id,
        user_id=user_id,
        sandbox_id=sandbox_id,
        size_gib=size_gib,
        storage_state=StorageState.ACTIVE,
        allocated_at=FIXED_NOW - timedelta(hours=1),
        last_metered_at=last_metered_at,
        gib_hours_consumed=gib_hours,
    )


def _make_plan(
    user_id: str = "user_01",
    tier: str = "pro",
    monthly_limit: Decimal = Decimal("100"),
    monthly_used: Decimal = Decimal("0"),
    grace_period_seconds: int = 1800,
    grace_period_started_at: datetime | None = None,
    warning_80_notified_at: datetime | None = None,
    warning_100_notified_at: datetime | None = None,
    period_end: datetime | None = None,
) -> UserPlan:
    return UserPlan(
        user_id=user_id,
        tier=tier,
        compute_units_monthly_limit=monthly_limit,
        compute_units_monthly_used=monthly_used,
        storage_capacity_limit_gib=10,
        max_concurrent_running=3,
        max_sandbox_duration_seconds=7200,
        allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"],
        grace_period_seconds=grace_period_seconds,
        grace_period_started_at=grace_period_started_at,
        warning_80_notified_at=warning_80_notified_at,
        warning_100_notified_at=warning_100_notified_at,
        period_start=datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        period_end=period_end or datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
    )


def _make_sandbox(
    sandbox_id: str = "sb_test01",
    user_id: str = "user_01",
    status: str = SandboxStatus.READY,
) -> Sandbox:
    sb = Sandbox()
    for k, v in {
        "id": sandbox_id,
        "name": "test-sandbox",
        "owner_id": user_id,
        "template": "aio-sandbox-small",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": status,
        "version": 1,
        "endpoints": {},
        "k8s_namespace": "treadstone-local",
        "persist": False,
        "storage_size": None,
        "provision_mode": "claim",
    }.items():
        setattr(sb, k, v)
    return sb


class _MockScalars:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def __iter__(self):
        return iter(self._items)


class _MockRowCount:
    def __init__(self, rowcount: int = 1):
        self.rowcount = rowcount


class _MockDistinct:
    def __init__(self, items):
        self._items = items

    def all(self):
        return [(i,) for i in self._items]


def _make_tick_session(open_sessions, update_rowcount=1, capture_update_stmts: list | None = None):
    """Create a mock session that supports begin_nested() savepoints for tick_metering tests."""
    session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _MockScalars(open_sessions)
        if capture_update_stmts is not None:
            capture_update_stmts.append(stmt)
        return _MockRowCount(update_rowcount)

    session.execute = AsyncMock(side_effect=mock_execute)
    session.commit = AsyncMock()

    nested_ctx = AsyncMock()
    nested_ctx.__aenter__ = AsyncMock(return_value=None)
    nested_ctx.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested_ctx)

    return session


# ═══════════════════════════════════════════════════════════
#  F18 — tick_metering
# ═══════════════════════════════════════════════════════════


class TestTickMetering:
    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_meters_open_session_and_updates_resource_hours(self, mock_now, mock_metering):
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session(last_metered_at=ONE_MINUTE_AGO, gmt_updated=ONE_MINUTE_AGO)
        captured: list = []
        session = _make_tick_session([cs], capture_update_stmts=captured)

        result = await tick_metering(session)

        assert result == 1
        session.commit.assert_awaited_once()
        assert len(captured) == 1
        elapsed_seconds = (FIXED_NOW - ONE_MINUTE_AGO).total_seconds()
        eh = Decimal(str(elapsed_seconds)) / Decimal("3600")
        _assert_tick_update_resource_hours(
            captured[0],
            expected_delta_vcpu=cs.vcpu_request * eh,
            expected_delta_mem=cs.memory_gib_request * eh,
        )

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_skips_session_with_zero_elapsed(self, mock_now, mock_metering):
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session(last_metered_at=FIXED_NOW, gmt_updated=FIXED_NOW)
        session = _make_tick_session([cs])

        result = await tick_metering(session)

        assert result == 0

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_handles_optimistic_lock_conflict_with_savepoint_rollback(self, mock_now, mock_metering):
        """Lock conflict rolls back the savepoint — that session is skipped without failing the tick."""
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session()
        session = _make_tick_session([cs], update_rowcount=0)

        result = await tick_metering(session)

        assert result == 0

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_open_sessions_is_noop(self, mock_now, mock_metering):
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        session = _make_tick_session([])

        result = await tick_metering(session)

        assert result == 0
        session.commit.assert_not_awaited()

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_crash_recovery_compensates_gap(self, mock_now, mock_metering):
        """After a 5-minute leader crash, tick should compute the full gap."""
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session(
            last_metered_at=FIVE_MINUTES_AGO,
            gmt_updated=FIVE_MINUTES_AGO,
        )
        elapsed_seconds = (FIXED_NOW - FIVE_MINUTES_AGO).total_seconds()
        eh = Decimal(str(elapsed_seconds)) / Decimal("3600")
        expected_delta_vcpu = cs.vcpu_request * eh
        expected_delta_mem = cs.memory_gib_request * eh

        captured: list = []
        session = _make_tick_session([cs], capture_update_stmts=captured)

        await tick_metering(session)

        assert len(captured) == 1
        _assert_tick_update_resource_hours(
            captured[0],
            expected_delta_vcpu=expected_delta_vcpu,
            expected_delta_mem=expected_delta_mem,
        )

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_tick_consumes_credits_per_user(self, mock_now, mock_metering):
        """tick_metering must call consume_compute_credits for each user with metered sessions."""
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session(last_metered_at=ONE_MINUTE_AGO, gmt_updated=ONE_MINUTE_AGO)
        session = _make_tick_session([cs])

        await tick_metering(session)

        mock_metering.consume_compute_credits.assert_awaited_once()
        call_args = mock_metering.consume_compute_credits.call_args
        assert call_args[0][0] is session
        assert call_args[0][1] == cs.user_id
        credit_amount = call_args[0][2]
        assert credit_amount > Decimal("0")

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_tick_aggregates_credits_across_sessions_for_same_user(self, mock_now, mock_metering):
        """Multiple sessions for the same user produce a single aggregated consume call."""
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs1 = _make_open_session(
            session_id="cs_01",
            sandbox_id="sb_01",
            user_id="user_01",
            last_metered_at=ONE_MINUTE_AGO,
            gmt_updated=ONE_MINUTE_AGO,
        )
        cs2 = _make_open_session(
            session_id="cs_02",
            sandbox_id="sb_02",
            user_id="user_01",
            last_metered_at=ONE_MINUTE_AGO,
            gmt_updated=ONE_MINUTE_AGO,
        )
        session = _make_tick_session([cs1, cs2])

        await tick_metering(session)

        mock_metering.consume_compute_credits.assert_awaited_once()
        call_args = mock_metering.consume_compute_credits.call_args
        assert call_args[0][1] == "user_01"

    @patch("treadstone.services.metering_tasks._metering")
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_tick_does_not_consume_credits_on_lock_conflict(self, mock_now, mock_metering):
        """If optimistic lock conflicts for all sessions, no credits should be consumed."""
        from treadstone.services.metering_tasks import tick_metering

        mock_metering.consume_compute_credits = AsyncMock()
        cs = _make_open_session()
        session = _make_tick_session([cs], update_rowcount=0)

        await tick_metering(session)

        mock_metering.consume_compute_credits.assert_not_awaited()


# ═══════════════════════════════════════════════════════════
#  F19 — tick_storage_metering
# ═══════════════════════════════════════════════════════════


class TestTickStorageMetering:
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_updates_gib_hours(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockRowCount(3))
        session.commit = AsyncMock()

        result = await tick_storage_metering(session)

        assert result == 3
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_rows_matched(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockRowCount(0))
        session.commit = AsyncMock()

        result = await tick_storage_metering(session)

        assert result == 0
        session.commit.assert_not_awaited()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_active_entries(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockRowCount(0))
        session.commit = AsyncMock()

        result = await tick_storage_metering(session)

        assert result == 0
        session.commit.assert_not_awaited()


# ═══════════════════════════════════════════════════════════
#  F22 — check_warning_thresholds
# ═══════════════════════════════════════════════════════════


class TestCheckWarningThresholds:
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_emits_80_percent_warning(self, mock_now):
        from treadstone.services.metering_tasks import check_warning_thresholds

        plan = _make_plan(monthly_limit=Decimal("100"), monthly_used=Decimal("85"))

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("15"))
            mock_metering.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_warning_thresholds(session)

                mock_audit.assert_awaited_once()
                assert mock_audit.call_args.kwargs["action"] == "metering.compute_warning_80"

        assert plan.warning_80_notified_at is not None

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_emits_100_percent_warning(self, mock_now):
        from treadstone.services.metering_tasks import check_warning_thresholds

        plan = _make_plan(monthly_limit=Decimal("100"), monthly_used=Decimal("100"))

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("-5"))
            mock_metering.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_warning_thresholds(session)

                mock_audit.assert_awaited_once()
                assert mock_audit.call_args.kwargs["action"] == "metering.compute_warning_100"

        assert plan.warning_100_notified_at is not None

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_does_not_repeat_warning(self, mock_now):
        from treadstone.services.metering_tasks import check_warning_thresholds

        plan = _make_plan(
            monthly_limit=Decimal("100"),
            monthly_used=Decimal("85"),
            warning_80_notified_at=FIXED_NOW - timedelta(hours=1),
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("15"))
            mock_metering.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_warning_thresholds(session)

                mock_audit.assert_not_awaited()


# ═══════════════════════════════════════════════════════════
#  F21 — check_grace_periods
# ═══════════════════════════════════════════════════════════


class TestCheckGracePeriods:
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_starts_grace_period_on_first_exhaustion(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        plan = _make_plan(grace_period_started_at=None)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("-1"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session)

                mock_audit.assert_awaited_once()
                assert mock_audit.call_args.kwargs["action"] == "metering.grace_period_started"

        assert plan.grace_period_started_at == FIXED_NOW

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_enforces_stop_after_grace_period_expires(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        grace_start = FIXED_NOW - timedelta(seconds=2000)
        plan = _make_plan(grace_period_seconds=1800, grace_period_started_at=grace_start)
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockDistinct(["user_01"])
            return _MockScalars([sandbox])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.get = AsyncMock(return_value=sandbox)
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("-5"))
            mock_metering.close_compute_session = AsyncMock(return_value=None)
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session)

                auto_stop_calls = [
                    c for c in mock_audit.call_args_list if c.kwargs.get("action") == "metering.auto_stop"
                ]
                assert len(auto_stop_calls) == 1
                assert auto_stop_calls[0].kwargs["metadata"]["reason"] == "grace_period_expired"

        assert plan.grace_period_started_at is None
        assert sandbox.status == SandboxStatus.STOPPED

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_enforces_stop_on_absolute_cap_exceeded(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        grace_start = FIXED_NOW - timedelta(seconds=60)
        plan = _make_plan(
            monthly_limit=Decimal("100"),
            grace_period_seconds=1800,
            grace_period_started_at=grace_start,
        )
        sandbox = _make_sandbox()

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockDistinct(["user_01"])
            return _MockScalars([sandbox])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.add = MagicMock()
        session.commit = AsyncMock()

        overage = Decimal("25")
        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=-overage)
            mock_metering.close_compute_session = AsyncMock(return_value=None)
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session)

                auto_stop_calls = [
                    c for c in mock_audit.call_args_list if c.kwargs.get("action") == "metering.auto_stop"
                ]
                assert len(auto_stop_calls) == 1
                assert auto_stop_calls[0].kwargs["metadata"]["reason"] == "absolute_cap_exceeded"

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_clears_grace_period_when_credits_restored(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        plan = _make_plan(grace_period_started_at=FIXED_NOW - timedelta(minutes=10))

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("50"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session)

                assert mock_audit.call_args.kwargs["action"] == "metering.grace_period_cleared"

        assert plan.grace_period_started_at is None

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_uses_stop_callback_when_provided(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        grace_start = FIXED_NOW - timedelta(seconds=2000)
        plan = _make_plan(grace_period_seconds=1800, grace_period_started_at=grace_start)
        sandbox = _make_sandbox()

        stop_callback = AsyncMock()

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockDistinct(["user_01"])
            return _MockScalars([sandbox])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=Decimal("-5"))
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session, stop_sandbox_callback=stop_callback)

        stop_callback.assert_awaited_once_with(session, sandbox)

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_running_sandboxes_is_noop(self, mock_now):
        from treadstone.services.metering_tasks import check_grace_periods

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct([]))
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering"):
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                await check_grace_periods(session)
                mock_audit.assert_not_awaited()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_does_not_enforce_during_active_grace_period(self, mock_now):
        """Grace period is active but not expired — no enforcement yet."""
        from treadstone.services.metering_tasks import check_grace_periods

        grace_start = FIXED_NOW - timedelta(seconds=60)
        plan = _make_plan(
            monthly_limit=Decimal("100"),
            grace_period_seconds=1800,
            grace_period_started_at=grace_start,
        )

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockDistinct(["user_01"]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        overage = Decimal("5")
        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.get_user_plan = AsyncMock(return_value=plan)
            mock_metering.get_total_compute_remaining = AsyncMock(return_value=-overage)
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                await check_grace_periods(session)
                auto_stop_calls = [
                    c for c in mock_audit.call_args_list if c.kwargs.get("action") == "metering.auto_stop"
                ]
                assert len(auto_stop_calls) == 0

        assert plan.grace_period_started_at == grace_start


# ═══════════════════════════════════════════════════════════
#  F23 — handle_period_rollover
# ═══════════════════════════════════════════════════════════


class TestHandlePeriodRollover:
    @patch("treadstone.services.metering_tasks.utc_now")
    async def test_splits_session_at_period_boundary(self, mock_now):
        from treadstone.services.metering_tasks import handle_period_rollover

        now = datetime(2026, 4, 1, 0, 5, 0, tzinfo=UTC)
        mock_now.return_value = now
        period_end = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)

        cs = _make_open_session(
            last_metered_at=datetime(2026, 3, 31, 23, 59, 0, tzinfo=UTC),
            template="aio-sandbox-medium",
        )
        plan = _make_plan(period_end=period_end, monthly_used=Decimal("50"))
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        session = AsyncMock()
        session.get = AsyncMock(return_value=sandbox)
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
            mock_audit.return_value = MagicMock()
            new_cs = await handle_period_rollover(session, cs, plan)

        assert cs.ended_at == period_end
        assert plan.compute_units_monthly_used == Decimal("0")
        assert plan.period_start == period_end
        assert plan.warning_80_notified_at is None
        assert plan.warning_100_notified_at is None
        assert new_cs is not None
        assert new_cs.started_at == period_end
        assert new_cs.vcpu_request == cs.vcpu_request
        assert new_cs.memory_gib_request == cs.memory_gib_request

    @patch("treadstone.services.metering_tasks.utc_now")
    async def test_no_rollover_when_within_period(self, mock_now):
        from treadstone.services.metering_tasks import handle_period_rollover

        mock_now.return_value = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)

        cs = _make_open_session()
        plan = _make_plan(period_end=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC))

        session = AsyncMock()
        result = await handle_period_rollover(session, cs, plan)

        assert result is None
        assert cs.ended_at is None

    @patch("treadstone.services.metering_tasks.utc_now")
    async def test_rollover_with_stopped_sandbox_returns_none(self, mock_now):
        from treadstone.services.metering_tasks import handle_period_rollover

        now = datetime(2026, 4, 1, 0, 5, 0, tzinfo=UTC)
        mock_now.return_value = now
        period_end = datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC)

        cs = _make_open_session(last_metered_at=datetime(2026, 3, 31, 23, 59, 0, tzinfo=UTC))
        plan = _make_plan(period_end=period_end)
        sandbox = _make_sandbox(status=SandboxStatus.STOPPED)

        session = AsyncMock()
        session.get = AsyncMock(return_value=sandbox)
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
            mock_audit.return_value = MagicMock()
            new_cs = await handle_period_rollover(session, cs, plan)

        assert cs.ended_at == period_end
        assert new_cs is None


class TestResetMonthlyCredits:
    @patch("treadstone.services.metering_tasks.utc_now")
    async def test_resets_expired_plans(self, mock_now):
        from treadstone.services.metering_tasks import reset_monthly_credits

        now = datetime(2026, 4, 1, 0, 5, 0, tzinfo=UTC)
        mock_now.return_value = now

        plan = _make_plan(
            period_end=datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
            monthly_used=Decimal("85"),
            warning_80_notified_at=FIXED_NOW,
        )

        session = AsyncMock()
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _MockScalars([plan])
            return _MockScalars([])

        session.execute = AsyncMock(side_effect=mock_execute)
        session.add = MagicMock()
        session.commit = AsyncMock()

        with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
            mock_audit.return_value = MagicMock()
            result = await reset_monthly_credits(session)

        assert result == 1
        assert plan.compute_units_monthly_used == Decimal("0")
        assert plan.warning_80_notified_at is None
        assert plan.warning_100_notified_at is None
        session.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════
#  F20 — run_metering_tick (unified entry point)
# ═══════════════════════════════════════════════════════════


class TestRunMeteringTick:
    async def test_calls_all_substeps(self):
        from treadstone.services.metering_tasks import run_metering_tick

        session = AsyncMock()
        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with (
            patch("treadstone.services.metering_tasks.tick_metering", new_callable=AsyncMock) as m1,
            patch("treadstone.services.metering_tasks.tick_storage_metering", new_callable=AsyncMock) as m2,
            patch("treadstone.services.metering_tasks.check_warning_thresholds", new_callable=AsyncMock) as m3,
            patch("treadstone.services.metering_tasks.check_grace_periods", new_callable=AsyncMock) as m4,
            patch("treadstone.services.metering_tasks.reset_monthly_credits", new_callable=AsyncMock) as m5,
        ):
            await run_metering_tick(session_factory)

            m1.assert_awaited_once()
            m2.assert_awaited_once()
            m3.assert_awaited_once()
            m4.assert_awaited_once()
            m5.assert_awaited_once()

    async def test_one_substep_failure_does_not_block_others(self):
        from treadstone.services.metering_tasks import run_metering_tick

        session = AsyncMock()
        factory = MagicMock()
        factory.__aenter__ = AsyncMock(return_value=session)
        factory.__aexit__ = AsyncMock(return_value=False)
        session_factory = MagicMock(return_value=factory)

        with (
            patch(
                "treadstone.services.metering_tasks.tick_metering",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB error"),
            ),
            patch("treadstone.services.metering_tasks.tick_storage_metering", new_callable=AsyncMock) as m2,
            patch("treadstone.services.metering_tasks.check_warning_thresholds", new_callable=AsyncMock) as m3,
            patch("treadstone.services.metering_tasks.check_grace_periods", new_callable=AsyncMock) as m4,
            patch("treadstone.services.metering_tasks.reset_monthly_credits", new_callable=AsyncMock) as m5,
        ):
            await run_metering_tick(session_factory)

            m2.assert_awaited_once()
            m3.assert_awaited_once()
            m4.assert_awaited_once()
            m5.assert_awaited_once()


# ═══════════════════════════════════════════════════════════
#  Sync supervisor metering integration
# ═══════════════════════════════════════════════════════════


class TestSyncSupervisorMeteringIntegration:
    async def test_supervisor_starts_metering_task_with_session_factory(self):
        from treadstone.services.sync_supervisor import LeaderControlledSyncSupervisor

        elector = AsyncMock()
        sync_loop = AsyncMock()
        session_factory = MagicMock()

        supervisor = LeaderControlledSyncSupervisor(
            elector=elector,
            sync_loop_factory=sync_loop,
            session_factory=session_factory,
        )

        assert supervisor._session_factory is session_factory

    async def test_supervisor_without_session_factory_has_no_metering(self):
        from treadstone.services.sync_supervisor import LeaderControlledSyncSupervisor

        elector = AsyncMock()
        sync_loop = AsyncMock()

        supervisor = LeaderControlledSyncSupervisor(
            elector=elector,
            sync_loop_factory=sync_loop,
        )

        assert supervisor._session_factory is None
        assert supervisor._metering_task is None
