"""Unit tests for metering background tasks (Layer 4: F18–F23)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from treadstone.models.metering import ComputeSession, StorageLedger, StorageState, UserPlan
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.services.metering_helpers import ConsumeResult

# ── Helpers ──────────────────────────────────────────────

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
ONE_MINUTE_AGO = FIXED_NOW - timedelta(seconds=60)
FIVE_MINUTES_AGO = FIXED_NOW - timedelta(minutes=5)


def _make_open_session(
    session_id: str = "cs_test01",
    sandbox_id: str = "sb_test01",
    user_id: str = "user_01",
    template: str = "aio-sandbox-small",
    rate: Decimal = Decimal("0.5"),
    last_metered_at: datetime = ONE_MINUTE_AGO,
    gmt_updated: datetime = ONE_MINUTE_AGO,
    credits_consumed: Decimal = Decimal("0"),
    credits_consumed_monthly: Decimal = Decimal("0"),
    credits_consumed_extra: Decimal = Decimal("0"),
) -> ComputeSession:
    return ComputeSession(
        id=session_id,
        sandbox_id=sandbox_id,
        user_id=user_id,
        template=template,
        credit_rate_per_hour=rate,
        started_at=FIXED_NOW - timedelta(hours=1),
        last_metered_at=last_metered_at,
        credits_consumed=credits_consumed,
        credits_consumed_monthly=credits_consumed_monthly,
        credits_consumed_extra=credits_consumed_extra,
        gmt_updated=gmt_updated,
    )


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
        compute_credits_monthly_limit=monthly_limit,
        compute_credits_monthly_used=monthly_used,
        storage_credits_monthly_limit=10,
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


def _make_tick_session(open_sessions, update_rowcount=1):
    """Create a mock session that supports begin_nested() savepoints for tick_metering tests."""
    session = AsyncMock()
    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _MockScalars(open_sessions)
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
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_meters_open_session_and_consumes_credits(self, mock_now):
        from treadstone.services.metering_tasks import tick_metering

        cs = _make_open_session(last_metered_at=ONE_MINUTE_AGO, gmt_updated=ONE_MINUTE_AGO)
        consume_result = ConsumeResult(monthly=Decimal("0.0083"), extra=Decimal("0"), shortfall=Decimal("0"))

        session = _make_tick_session([cs])

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock(return_value=consume_result)
            result = await tick_metering(session)

        assert result == 1
        mock_metering.consume_compute_credits.assert_awaited_once()
        session.commit.assert_awaited_once()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_skips_session_with_zero_elapsed(self, mock_now):
        from treadstone.services.metering_tasks import tick_metering

        cs = _make_open_session(last_metered_at=FIXED_NOW, gmt_updated=FIXED_NOW)
        session = _make_tick_session([cs])

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock()
            result = await tick_metering(session)

        assert result == 0
        mock_metering.consume_compute_credits.assert_not_awaited()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_handles_optimistic_lock_conflict_with_savepoint_rollback(self, mock_now):
        """Lock conflict rolls back the savepoint — consume side-effects are reverted."""
        from treadstone.services.metering_tasks import tick_metering

        cs = _make_open_session()
        consume_result = ConsumeResult(monthly=Decimal("0.0083"), extra=Decimal("0"), shortfall=Decimal("0"))

        session = _make_tick_session([cs], update_rowcount=0)

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock(return_value=consume_result)
            result = await tick_metering(session)

        assert result == 0

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_open_sessions_is_noop(self, mock_now):
        from treadstone.services.metering_tasks import tick_metering

        session = _make_tick_session([])

        with patch("treadstone.services.metering_tasks._metering"):
            result = await tick_metering(session)

        assert result == 0
        session.commit.assert_not_awaited()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_crash_recovery_compensates_gap(self, mock_now):
        """After a 5-minute leader crash, tick should compute the full gap."""
        from treadstone.services.metering_tasks import tick_metering

        cs = _make_open_session(
            last_metered_at=FIVE_MINUTES_AGO,
            gmt_updated=FIVE_MINUTES_AGO,
            rate=Decimal("0.5"),
        )
        expected_credits = Decimal("300") / Decimal("3600") * Decimal("0.5")

        captured_amount = None

        async def capture_consume(session, user_id, amount):
            nonlocal captured_amount
            captured_amount = amount
            return ConsumeResult(monthly=amount, extra=Decimal("0"), shortfall=Decimal("0"))

        session = _make_tick_session([cs])

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock(side_effect=capture_consume)
            await tick_metering(session)

        assert captured_amount is not None
        assert abs(captured_amount - expected_credits) < Decimal("0.0001")


# ═══════════════════════════════════════════════════════════
#  F19 — tick_storage_metering
# ═══════════════════════════════════════════════════════════


class TestTickStorageMetering:
    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_updates_gib_hours(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        entry = _make_storage_entry(size_gib=10, last_metered_at=ONE_MINUTE_AGO)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockScalars([entry]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await tick_storage_metering(session)

        assert result == 1
        expected_gib_hours = Decimal("10") * Decimal("60") / Decimal("3600")
        assert abs(entry.gib_hours_consumed - expected_gib_hours.quantize(Decimal("0.0001"))) < Decimal("0.001")
        session.commit.assert_awaited_once()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_skips_zero_elapsed(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        entry = _make_storage_entry(last_metered_at=FIXED_NOW)

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockScalars([entry]))
        session.add = MagicMock()
        session.commit = AsyncMock()

        result = await tick_storage_metering(session)

        assert result == 0
        session.commit.assert_not_awaited()

    @patch("treadstone.services.metering_tasks.utc_now", return_value=FIXED_NOW)
    async def test_no_active_entries(self, mock_now):
        from treadstone.services.metering_tasks import tick_storage_metering

        session = AsyncMock()
        session.execute = AsyncMock(return_value=_MockScalars([]))
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
            mock_metering.get_extra_credits_remaining = AsyncMock(return_value=Decimal("0"))
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
            mock_metering.get_extra_credits_remaining = AsyncMock(return_value=Decimal("0"))
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
            mock_metering.get_extra_credits_remaining = AsyncMock(return_value=Decimal("0"))
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
            rate=Decimal("2.0"),
        )
        plan = _make_plan(period_end=period_end, monthly_used=Decimal("50"))
        sandbox = _make_sandbox(status=SandboxStatus.READY)

        consume_result = ConsumeResult(monthly=Decimal("0.0333"), extra=Decimal("0"), shortfall=Decimal("0"))

        session = AsyncMock()
        session.get = AsyncMock(return_value=sandbox)
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock(return_value=consume_result)
            with patch("treadstone.services.metering_tasks.record_audit_event") as mock_audit:
                mock_audit.return_value = MagicMock()
                new_cs = await handle_period_rollover(session, cs, plan)

        assert cs.ended_at == period_end
        assert plan.compute_credits_monthly_used == Decimal("0")
        assert plan.period_start == period_end
        assert plan.warning_80_notified_at is None
        assert plan.warning_100_notified_at is None
        assert new_cs is not None
        assert new_cs.started_at == period_end

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

        consume_result = ConsumeResult(monthly=Decimal("0"), extra=Decimal("0"), shortfall=Decimal("0"))

        session = AsyncMock()
        session.get = AsyncMock(return_value=sandbox)
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch("treadstone.services.metering_tasks._metering") as mock_metering:
            mock_metering.consume_compute_credits = AsyncMock(return_value=consume_result)
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
        assert plan.compute_credits_monthly_used == Decimal("0")
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
