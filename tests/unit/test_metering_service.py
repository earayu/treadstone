"""Unit tests for MeteringService (Layer 1: F05–F09, Layer 2: F10–F14)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from treadstone.core.errors import (
    BadRequestError,
    ComputeQuotaExceededError,
    ConcurrentLimitError,
    NotFoundError,
    StorageQuotaExceededError,
    TemplateNotAllowedError,
    ValidationError,
)
from treadstone.models.metering import (
    ComputeGrant,
    ComputeSession,
    StorageLedger,
    StorageState,
    TierTemplate,
    UserPlan,
)
from treadstone.services.metering_helpers import ConsumeResult
from treadstone.services.metering_service import (
    WELCOME_BONUS_AMOUNT,
    WELCOME_BONUS_EXPIRY_DAYS,
    MeteringService,
)

FIXED_NOW = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)


# ── Helpers ────────────────────────────────────────────


def _make_template(tier_name: str = "free", **kwargs) -> TierTemplate:
    defaults = {
        "free": {
            "compute_units_monthly": Decimal("10"),
            "storage_capacity_gib": 0,
            "max_concurrent_running": 1,
            "max_sandbox_duration_seconds": 7200,
            "allowed_templates": ["aio-sandbox-tiny"],
            "grace_period_seconds": 900,
        },
        "pro": {
            "compute_units_monthly": Decimal("180"),
            "storage_capacity_gib": 20,
            "max_concurrent_running": 5,
            "max_sandbox_duration_seconds": 0,
            "allowed_templates": ["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"],
            "grace_period_seconds": 7200,
        },
    }
    values = {**defaults.get(tier_name, defaults["free"]), **kwargs}
    return TierTemplate(tier_name=tier_name, **values)


def _make_plan(user_id: str = "user01", tier: str = "free", **kwargs) -> UserPlan:
    defaults = {
        "tier": tier,
        "compute_units_monthly_limit": Decimal("10"),
        "compute_units_monthly_used": Decimal("0"),
        "storage_capacity_limit_gib": 0,
        "max_concurrent_running": 1,
        "max_sandbox_duration_seconds": 7200,
        "allowed_templates": ["aio-sandbox-tiny"],
        "grace_period_seconds": 900,
        "period_start": datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        "period_end": datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return UserPlan(user_id=user_id, **defaults)


class _MockResult:
    """Minimal mock for SQLAlchemy async Result."""

    def __init__(self, value=None, scalars_list=None, one_value=None):
        self._value = value
        self._scalars_list = scalars_list
        self._one_value = one_value if one_value is not None else value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def one_or_none(self):
        return self._one_value

    def one(self):
        return self._one_value

    def scalars(self):
        return self

    def all(self):
        return self._scalars_list if self._scalars_list is not None else []


class _AsyncNoop:
    """Minimal async context manager that propagates exceptions (mimics a savepoint)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _mock_session(*execute_returns: _MockResult) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(execute_returns))
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.begin_nested = MagicMock(return_value=_AsyncNoop())
    return session


def _added_objects(session: AsyncMock, cls=None):
    """Return all objects passed to session.add(), optionally filtered by type."""
    objs = [c.args[0] for c in session.add.call_args_list]
    if cls is not None:
        objs = [o for o in objs if isinstance(o, cls)]
    return objs


# ═══════════════════════════════════════════════════════
#  F05 — ensure_user_plan / get_user_plan / update_user_tier
# ═══════════════════════════════════════════════════════


class TestEnsureUserPlan:
    async def test_returns_existing_plan(self):
        existing_plan = _make_plan("user01")
        session = _mock_session(_MockResult(value=existing_plan))
        svc = MeteringService()

        plan = await svc.ensure_user_plan(session, "user01")

        assert plan is existing_plan
        session.flush.assert_not_awaited()

    async def test_creates_new_free_plan(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        template = _make_template("free")
        session = _mock_session(
            _MockResult(value=None),  # no existing plan
            _MockResult(value=template),  # tier template lookup
        )
        svc = MeteringService()

        plan = await svc.ensure_user_plan(session, "user01", tier="free")

        assert plan.user_id == "user01"
        assert plan.tier == "free"
        assert plan.compute_units_monthly_limit == Decimal("10")
        assert plan.period_start == datetime(2026, 3, 1, tzinfo=UTC)
        assert plan.period_end == datetime(2026, 4, 1, tzinfo=UTC)

        grants = _added_objects(session, ComputeGrant)
        assert len(grants) == 0
        session.flush.assert_awaited_once()

    async def test_creates_pro_plan_without_welcome_bonus(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        template = _make_template("pro")
        session = _mock_session(
            _MockResult(value=None),
            _MockResult(value=template),
        )
        svc = MeteringService()

        plan = await svc.ensure_user_plan(session, "user01", tier="pro")

        assert plan.tier == "pro"
        assert plan.compute_units_monthly_limit == Decimal("180")
        grants = _added_objects(session, ComputeGrant)
        assert len(grants) == 0

    async def test_invalid_tier_raises(self):
        session = _mock_session(
            _MockResult(value=None),  # no existing plan
            _MockResult(value=None),  # template not found
        )
        svc = MeteringService()

        with pytest.raises(NotFoundError, match="TierTemplate"):
            await svc.ensure_user_plan(session, "user01", tier="nonexistent")

    async def test_concurrent_creation_returns_winner(self, monkeypatch):
        """When a concurrent request already created the plan, return it."""
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        template = _make_template("free")
        winner_plan = _make_plan("user01")

        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=template)

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _MockResult(value=None),  # initial check: no plan
                _MockResult(value=winner_plan),  # re-query after IntegrityError
            ]
        )
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception("unique")))
        session.begin_nested = MagicMock(return_value=_AsyncNoop())

        result = await svc.ensure_user_plan(session, "user01", tier="free")

        assert result is winner_plan


class TestGetUserPlan:
    async def test_delegates_to_ensure(self, monkeypatch):
        """get_user_plan is a convenience alias for ensure_user_plan(tier='free')."""
        svc = MeteringService()
        sentinel = _make_plan("user01")
        svc.ensure_user_plan = AsyncMock(return_value=sentinel)

        result = await svc.get_user_plan(AsyncMock(), "user01")

        assert result is sentinel
        svc.ensure_user_plan.assert_awaited_once()


class TestUpdateUserTier:
    async def test_updates_existing_plan_from_template(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        old_plan = _make_plan("user01", tier="free")
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)
        session = _mock_session(
            _MockResult(value=old_plan),  # existing plan lookup
        )

        plan = await svc.update_user_tier(session, "user01", "pro")

        assert plan.tier == "pro"
        assert plan.compute_units_monthly_limit == Decimal("180")
        assert plan.storage_capacity_limit_gib == 20
        assert plan.max_concurrent_running == 5
        assert plan.max_sandbox_duration_seconds == 0
        assert plan.gmt_updated == FIXED_NOW

    async def test_applies_overrides(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        old_plan = _make_plan("user01", tier="free")
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)
        session = _mock_session(
            _MockResult(value=old_plan),  # existing plan lookup
        )

        overrides = {"compute_units_monthly_limit": Decimal("500"), "max_concurrent_running": 10}
        plan = await svc.update_user_tier(session, "user01", "pro", overrides=overrides)

        assert plan.compute_units_monthly_limit == Decimal("500")
        assert plan.max_concurrent_running == 10
        assert plan.overrides == overrides

    async def test_creates_with_target_tier_when_no_plan(self, monkeypatch):
        """First-time tier assignment should NOT create a free plan + bonus first."""
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)

        created_plan = _make_plan("user01", tier="pro", compute_units_monthly_limit=Decimal("180"))
        svc.ensure_user_plan = AsyncMock(return_value=created_plan)

        session = _mock_session(
            _MockResult(value=None),  # no existing plan
        )

        plan = await svc.update_user_tier(session, "user01", "pro")

        assert plan.tier == "pro"
        assert plan.gmt_updated == FIXED_NOW
        svc.ensure_user_plan.assert_awaited_once_with(session, "user01", tier="pro")

    async def test_corrects_tier_when_concurrent_free_plan_created(self, monkeypatch):
        """If ensure_user_plan returns a free plan (concurrent race), still apply the requested tier."""
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        pro_template = _make_template("pro")
        free_plan = _make_plan("user01", tier="free")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)
        svc.ensure_user_plan = AsyncMock(return_value=free_plan)
        session = _mock_session(
            _MockResult(value=None),  # no existing plan
        )

        plan = await svc.update_user_tier(session, "user01", "pro")

        assert plan.tier == "pro"
        assert plan.compute_units_monthly_limit == Decimal("180")
        assert plan.max_concurrent_running == 5


class TestApplyOverrides:
    def test_valid_keys(self):
        plan = _make_plan()
        MeteringService.apply_overrides(plan, {"max_concurrent_running": 99})
        assert plan.max_concurrent_running == 99

    def test_invalid_key_raises(self):
        plan = _make_plan()
        with pytest.raises(ValidationError, match="Invalid override key"):
            MeteringService.apply_overrides(plan, {"bogus_field": 1})

    def test_all_allowed_keys_accepted(self):
        plan = _make_plan()
        overrides = {
            "compute_units_monthly_limit": Decimal("999"),
            "storage_capacity_limit_gib": 999,
            "max_concurrent_running": 99,
            "max_sandbox_duration_seconds": 99999,
            "allowed_templates": ["aio-sandbox-tiny"],
            "grace_period_seconds": 9999,
        }
        MeteringService.apply_overrides(plan, overrides)
        for key, value in overrides.items():
            assert getattr(plan, key) == value


# ═══════════════════════════════════════════════════════
#  F06 — Welcome Bonus
# ═══════════════════════════════════════════════════════


class TestWelcomeBonus:
    def test_grant_fields(self):
        session = MagicMock()
        now = FIXED_NOW
        grant = MeteringService._create_welcome_bonus(session, "user01", now)

        assert grant.user_id == "user01"
        assert grant.grant_type == "welcome_bonus"
        assert grant.original_amount == WELCOME_BONUS_AMOUNT
        assert grant.remaining_amount == WELCOME_BONUS_AMOUNT
        assert grant.expires_at == now + timedelta(days=WELCOME_BONUS_EXPIRY_DAYS)
        session.add.assert_called_once_with(grant)


# ═══════════════════════════════════════════════════════
#  F07 — consume_compute_credits
# ═══════════════════════════════════════════════════════


class TestConsumeComputeCredits:
    async def test_zero_amount_is_noop(self):
        svc = MeteringService()
        result = await svc.consume_compute_credits(AsyncMock(), "user01", Decimal("0"))
        assert result == ConsumeResult(Decimal("0"), Decimal("0"), Decimal("0"))

    async def test_negative_amount_is_noop(self):
        svc = MeteringService()
        result = await svc.consume_compute_credits(AsyncMock(), "user01", Decimal("-5"))
        assert result == ConsumeResult(Decimal("0"), Decimal("0"), Decimal("0"))

    async def test_fully_covered_by_monthly(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("50"),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session()

        result = await svc.consume_compute_credits(session, "user01", Decimal("10"))

        assert result.monthly == Decimal("10")
        assert result.extra == Decimal("0")
        assert result.shortfall == Decimal("0")
        assert plan.compute_units_monthly_used == Decimal("60")

    async def test_monthly_plus_extra(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("98"),
        )
        grant = ComputeGrant(
            user_id="user01",
            grant_type="welcome_bonus",
            original_amount=Decimal("50"),
            remaining_amount=Decimal("50"),
            granted_at=FIXED_NOW,
            expires_at=FIXED_NOW + timedelta(days=90),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session(_MockResult(scalars_list=[grant]))

        result = await svc.consume_compute_credits(session, "user01", Decimal("5"))

        assert result.monthly == Decimal("2")
        assert result.extra == Decimal("3")
        assert result.shortfall == Decimal("0")
        assert plan.compute_units_monthly_used == Decimal("100")
        assert grant.remaining_amount == Decimal("47")

    async def test_both_pools_exhausted_returns_shortfall(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("10"),
            compute_units_monthly_used=Decimal("10"),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session(_MockResult(scalars_list=[]))

        result = await svc.consume_compute_credits(session, "user01", Decimal("5"))

        assert result.monthly == Decimal("0")
        assert result.extra == Decimal("0")
        assert result.shortfall == Decimal("5")

    async def test_extra_fifo_consumes_nearest_expiry_first(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("10"),
            compute_units_monthly_used=Decimal("10"),
        )
        grant_soon = ComputeGrant(
            user_id="user01",
            grant_type="campaign",
            original_amount=Decimal("3"),
            remaining_amount=Decimal("3"),
            granted_at=FIXED_NOW,
            expires_at=FIXED_NOW + timedelta(days=7),
        )
        grant_later = ComputeGrant(
            user_id="user01",
            grant_type="admin_grant",
            original_amount=Decimal("20"),
            remaining_amount=Decimal("20"),
            granted_at=FIXED_NOW,
            expires_at=FIXED_NOW + timedelta(days=180),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session(_MockResult(scalars_list=[grant_soon, grant_later]))

        result = await svc.consume_compute_credits(session, "user01", Decimal("5"))

        assert result.extra == Decimal("5")
        assert grant_soon.remaining_amount == Decimal("0")
        assert grant_later.remaining_amount == Decimal("18")

    async def test_monthly_already_exceeded_skips_monthly(self, monkeypatch):
        """If monthly_used > limit (shouldn't happen normally), don't go negative."""
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("10"),
            compute_units_monthly_used=Decimal("12"),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session(_MockResult(scalars_list=[]))

        result = await svc.consume_compute_credits(session, "user01", Decimal("5"))

        assert result.monthly == Decimal("0")
        assert result.shortfall == Decimal("5")


# ═══════════════════════════════════════════════════════
#  F08 — open / close compute session
# ═══════════════════════════════════════════════════════


class TestOpenComputeSession:
    async def test_creates_session_with_correct_fields(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        session = _mock_session(
            _MockResult(value=None),  # no existing open session
        )
        svc = MeteringService()

        cs = await svc.open_compute_session(session, "sb01", "user01", "aio-sandbox-small")

        assert cs.sandbox_id == "sb01"
        assert cs.user_id == "user01"
        assert cs.template == "aio-sandbox-small"
        assert cs.vcpu_request == Decimal("0.5")
        assert cs.memory_gib_request == Decimal("2")
        assert cs.started_at == FIXED_NOW
        assert cs.last_metered_at == FIXED_NOW
        assert cs.ended_at is None
        session.flush.assert_awaited_once()

    async def test_returns_existing_open_session(self):
        """Idempotent: return existing open session instead of creating a duplicate."""
        existing = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="aio-sandbox-small",
            vcpu_request=Decimal("0.5"),
            memory_gib_request=Decimal("2"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
        )
        session = _mock_session(_MockResult(value=existing))
        svc = MeteringService()

        cs = await svc.open_compute_session(session, "sb01", "user01", "aio-sandbox-small")

        assert cs is existing
        session.flush.assert_not_awaited()

    async def test_unknown_template_raises(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=None))
        with pytest.raises(BadRequestError, match="Unknown sandbox template"):
            await svc.open_compute_session(session, "sb01", "user01", "nonexistent")


class TestCloseComputeSession:
    async def test_no_open_session_returns_none(self):
        session = _mock_session(_MockResult(value=None))
        svc = MeteringService()

        result = await svc.close_compute_session(session, "sb01")

        assert result is None

    async def test_closes_session_and_accumulates_resource_hours(self, monkeypatch):
        last_tick = datetime(2026, 3, 15, 9, 59, 0, tzinfo=UTC)
        close_time = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: close_time)

        cs = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="aio-sandbox-small",
            vcpu_request=Decimal("0.5"),
            memory_gib_request=Decimal("2"),
            started_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
            last_metered_at=last_tick,
            vcpu_hours=Decimal("0"),
            memory_gib_hours=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=cs))
        svc = MeteringService()
        svc.consume_compute_credits = AsyncMock(return_value=ConsumeResult(Decimal("0"), Decimal("0"), Decimal("0")))

        result = await svc.close_compute_session(session, "sb01")

        assert result is cs
        assert cs.ended_at == close_time
        assert cs.last_metered_at == close_time
        eh = Decimal("60") / Decimal("3600")
        assert abs(cs.vcpu_hours - Decimal("0.5") * eh) < Decimal("0.0001")
        assert abs(cs.memory_gib_hours - Decimal("2") * eh) < Decimal("0.0001")

    async def test_close_consumes_credits_for_final_delta(self, monkeypatch):
        """Closing a session with elapsed time must consume credits via dual-pool."""
        last_tick = datetime(2026, 3, 15, 9, 59, 0, tzinfo=UTC)
        close_time = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: close_time)

        cs = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="aio-sandbox-small",
            vcpu_request=Decimal("0.5"),
            memory_gib_request=Decimal("2"),
            started_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
            last_metered_at=last_tick,
            vcpu_hours=Decimal("0"),
            memory_gib_hours=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=cs))
        svc = MeteringService()
        svc.consume_compute_credits = AsyncMock(return_value=ConsumeResult(Decimal("0"), Decimal("0"), Decimal("0")))

        await svc.close_compute_session(session, "sb01")

        svc.consume_compute_credits.assert_awaited_once()
        call_args = svc.consume_compute_credits.call_args
        assert call_args[0][1] == "user01"
        credit_amount = call_args[0][2]
        assert credit_amount > Decimal("0")

    async def test_zero_elapsed_still_closes(self, monkeypatch):
        """If last_metered_at == now, no resource-hours are added but session still closes."""
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        cs = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="aio-sandbox-tiny",
            vcpu_request=Decimal("0.25"),
            memory_gib_request=Decimal("0.5"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
            vcpu_hours=Decimal("0"),
            memory_gib_hours=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=cs))
        svc = MeteringService()

        result = await svc.close_compute_session(session, "sb01")

        assert result.ended_at == FIXED_NOW
        assert result.vcpu_hours == Decimal("0")
        assert result.memory_gib_hours == Decimal("0")


# ═══════════════════════════════════════════════════════
#  F09 — storage allocation / release
# ═══════════════════════════════════════════════════════


class TestRecordStorageAllocation:
    async def test_creates_active_ledger_entry(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        # Idempotency: first execute checks for existing ACTIVE ledger (none)
        session = _mock_session(_MockResult(value=None))
        svc = MeteringService()

        ledger = await svc.record_storage_allocation(session, "user01", "sb01", 10)

        assert ledger.user_id == "user01"
        assert ledger.sandbox_id == "sb01"
        assert ledger.size_gib == 10
        assert ledger.storage_state == StorageState.ACTIVE
        assert ledger.allocated_at == FIXED_NOW
        assert ledger.last_metered_at == FIXED_NOW
        assert ledger.released_at is None
        session.flush.assert_awaited_once()


class TestRecordStorageRelease:
    async def test_no_active_entry_returns_none(self):
        session = _mock_session(_MockResult(value=None))
        svc = MeteringService()

        result = await svc.record_storage_release(session, "sb01")

        assert result is None

    async def test_transitions_to_deleted_with_gib_hours(self, monkeypatch):
        allocated = datetime(2026, 3, 14, 10, 0, 0, tzinfo=UTC)
        release_time = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: release_time)

        ledger = StorageLedger(
            user_id="user01",
            sandbox_id="sb01",
            size_gib=10,
            storage_state=StorageState.ACTIVE,
            allocated_at=allocated,
            last_metered_at=allocated,
            gib_hours_consumed=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=ledger))
        svc = MeteringService()

        result = await svc.record_storage_release(session, "sb01")

        assert result is ledger
        assert ledger.storage_state == StorageState.DELETED
        assert ledger.released_at == release_time
        # 24 hours * 10 GiB = 240 GiB-hours
        assert ledger.gib_hours_consumed == Decimal("240.0000")

    async def test_zero_elapsed_no_additional_gib_hours(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        ledger = StorageLedger(
            user_id="user01",
            sandbox_id="sb01",
            size_gib=5,
            storage_state=StorageState.ACTIVE,
            allocated_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
            gib_hours_consumed=Decimal("100.0000"),
        )
        session = _mock_session(_MockResult(value=ledger))
        svc = MeteringService()

        result = await svc.record_storage_release(session, "sb01")

        assert result.storage_state == StorageState.DELETED
        assert result.gib_hours_consumed == Decimal("100.0000")


# ═══════════════════════════════════════════════════════
#  F10 — check_template_allowed
# ═══════════════════════════════════════════════════════


class TestCheckTemplateAllowed:
    async def test_allowed_template_passes(self):
        plan = _make_plan("user01", allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium"])
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        await svc.check_template_allowed(AsyncMock(), "user01", "aio-sandbox-small")

    async def test_disallowed_template_raises(self):
        plan = _make_plan("user01", tier="free", allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small"])
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        with pytest.raises(TemplateNotAllowedError) as exc_info:
            await svc.check_template_allowed(AsyncMock(), "user01", "aio-sandbox-medium")
        assert exc_info.value.status == 403
        assert "aio-sandbox-medium" in exc_info.value.message
        assert "free" in exc_info.value.message

    async def test_empty_allowed_list_always_raises(self):
        plan = _make_plan("user01", allowed_templates=[])
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        with pytest.raises(TemplateNotAllowedError) as exc_info:
            await svc.check_template_allowed(AsyncMock(), "user01", "aio-sandbox-tiny")
        assert "Allowed templates: none" in exc_info.value.message

    async def test_all_allowed_templates_pass(self):
        templates = ["aio-sandbox-tiny", "aio-sandbox-small", "aio-sandbox-medium", "aio-sandbox-large"]
        plan = _make_plan("user01", allowed_templates=templates)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        for tmpl in templates:
            await svc.check_template_allowed(AsyncMock(), "user01", tmpl)


# ═══════════════════════════════════════════════════════
#  F11 — check_compute_quota / get_total_compute_remaining
# ═══════════════════════════════════════════════════════


class TestCheckComputeQuota:
    async def test_sufficient_monthly_passes(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("50"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        await svc.check_compute_quota(AsyncMock(), "user01")

    async def test_monthly_exhausted_but_extra_available(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("100"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("50"))

        await svc.check_compute_quota(AsyncMock(), "user01")

    async def test_both_exhausted_raises(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("100"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        with pytest.raises(ComputeQuotaExceededError) as exc_info:
            await svc.check_compute_quota(AsyncMock(), "user01")
        assert exc_info.value.status == 402
        assert "100.0 / 100.0" in exc_info.value.message

    async def test_exactly_zero_remaining_raises(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("10"),
            compute_units_monthly_used=Decimal("10"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        with pytest.raises(ComputeQuotaExceededError):
            await svc.check_compute_quota(AsyncMock(), "user01")

    async def test_negative_monthly_but_extra_covers(self):
        """Grace period overage: monthly_used > limit, but extra credits compensate."""
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("105"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("10"))

        await svc.check_compute_quota(AsyncMock(), "user01")

    async def test_error_includes_extra_remaining(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("50"),
            compute_units_monthly_used=Decimal("50"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        with pytest.raises(ComputeQuotaExceededError) as exc_info:
            await svc.check_compute_quota(AsyncMock(), "user01")
        assert "extra remaining: 0.0" in exc_info.value.message

    async def test_outstanding_overage_blocks_even_with_partial_extra_recovery(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("50"),
            compute_units_monthly_used=Decimal("50"),
            compute_units_overage=Decimal("8"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("5"))

        with pytest.raises(ComputeQuotaExceededError):
            await svc.check_compute_quota(AsyncMock(), "user01")


class TestGetTotalComputeRemaining:
    async def test_monthly_plus_extra(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("60"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("50"))

        result = await svc.get_total_compute_remaining(AsyncMock(), "user01")
        assert result == Decimal("90")

    async def test_overspent_returns_negative(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("110"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        result = await svc.get_total_compute_remaining(AsyncMock(), "user01")
        assert result == Decimal("-10")

    async def test_no_extra_credits(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("0"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("0"))

        result = await svc.get_total_compute_remaining(AsyncMock(), "user01")
        assert result == Decimal("100")

    async def test_monthly_unused_plus_large_extra(self):
        plan = _make_plan(
            "user01",
            compute_units_monthly_limit=Decimal("100"),
            compute_units_monthly_used=Decimal("0"),
        )
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_compute_remaining = AsyncMock(return_value=Decimal("200"))

        result = await svc.get_total_compute_remaining(AsyncMock(), "user01")
        assert result == Decimal("300")


# ═══════════════════════════════════════════════════════
#  F12 — check_concurrent_limit
# ═══════════════════════════════════════════════════════


class TestCheckConcurrentLimit:
    async def test_under_limit_passes(self):
        plan = _make_plan("user01", max_concurrent_running=3)
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        svc._count_running_sandboxes = AsyncMock(return_value=1)

        await svc.check_concurrent_limit(AsyncMock(), "user01")

    async def test_zero_running_passes(self):
        plan = _make_plan("user01", max_concurrent_running=1)
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        svc._count_running_sandboxes = AsyncMock(return_value=0)

        await svc.check_concurrent_limit(AsyncMock(), "user01")

    async def test_at_limit_raises(self):
        plan = _make_plan("user01", max_concurrent_running=3)
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        svc._count_running_sandboxes = AsyncMock(return_value=3)

        with pytest.raises(ConcurrentLimitError) as exc_info:
            await svc.check_concurrent_limit(AsyncMock(), "user01")
        assert exc_info.value.status == 429
        assert "3 / 3" in exc_info.value.message

    async def test_over_limit_raises(self):
        plan = _make_plan("user01", max_concurrent_running=3)
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        svc._count_running_sandboxes = AsyncMock(return_value=5)

        with pytest.raises(ConcurrentLimitError):
            await svc.check_concurrent_limit(AsyncMock(), "user01")

    async def test_single_slot_tier(self):
        plan = _make_plan("user01", max_concurrent_running=1)
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        svc._count_running_sandboxes = AsyncMock(return_value=1)

        with pytest.raises(ConcurrentLimitError) as exc_info:
            await svc.check_concurrent_limit(AsyncMock(), "user01")
        assert "1 / 1" in exc_info.value.message


class TestCountRunningSandboxes:
    async def test_returns_count(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=3))

        result = await svc._count_running_sandboxes(session, "user01")
        assert result == 3

    async def test_zero_when_none_running(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=0))

        result = await svc._count_running_sandboxes(session, "user01")
        assert result == 0


# ═══════════════════════════════════════════════════════
#  F13 — check_storage_quota / get_total_storage_quota / get_current_storage_used
# ═══════════════════════════════════════════════════════


class TestCheckStorageQuota:
    async def test_sufficient_quota_passes(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)
        svc.get_current_storage_used = AsyncMock(return_value=3)

        await svc.check_storage_quota(AsyncMock(), "user01", requested_gib=5)

    async def test_exact_fit_passes(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)
        svc.get_current_storage_used = AsyncMock(return_value=5)

        await svc.check_storage_quota(AsyncMock(), "user01", requested_gib=5)

    async def test_insufficient_quota_raises(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)
        svc.get_current_storage_used = AsyncMock(return_value=8)

        with pytest.raises(StorageQuotaExceededError) as exc_info:
            await svc.check_storage_quota(AsyncMock(), "user01", requested_gib=5)
        assert exc_info.value.status == 402
        assert "8 GiB" in exc_info.value.message
        assert "5 GiB" in exc_info.value.message
        assert "10 GiB" in exc_info.value.message

    async def test_zero_quota_raises(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=0)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)
        svc.get_current_storage_used = AsyncMock(return_value=0)

        with pytest.raises(StorageQuotaExceededError):
            await svc.check_storage_quota(AsyncMock(), "user01", requested_gib=5)

    async def test_overcommitted_storage_raises(self):
        """Post-downgrade scenario: current_used > total_quota."""
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)
        svc.get_current_storage_used = AsyncMock(return_value=40)

        with pytest.raises(StorageQuotaExceededError):
            await svc.check_storage_quota(AsyncMock(), "user01", requested_gib=1)


class TestGetTotalStorageQuota:
    async def test_monthly_only(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=0)

        result = await svc.get_total_storage_quota(AsyncMock(), "user01")
        assert result == 10

    async def test_monthly_plus_extra(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=10)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=5)

        result = await svc.get_total_storage_quota(AsyncMock(), "user01")
        assert result == 15

    async def test_zero_monthly_with_extra(self):
        plan = _make_plan("user01", storage_capacity_limit_gib=0)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)
        svc.get_extra_storage_quota = AsyncMock(return_value=20)

        result = await svc.get_total_storage_quota(AsyncMock(), "user01")
        assert result == 20


class TestGetCurrentStorageUsed:
    async def test_with_active_entries(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=15))

        result = await svc.get_current_storage_used(session, "user01")
        assert result == 15

    async def test_no_entries_returns_zero(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=0))

        result = await svc.get_current_storage_used(session, "user01")
        assert result == 0


class TestUsageSummaryQueries:
    async def test_snapshot_batches_usage_rollups(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan("user01", storage_capacity_limit_gib=10, max_concurrent_running=3)
        svc = MeteringService()
        session = _mock_session(
            _MockResult(one_value=(plan, 5, 2, 1, Decimal("7.5"))),
        )

        snapshot = await svc._get_usage_summary_snapshot(session, "user01")

        assert snapshot == (plan, 5, 2, 1, Decimal("7.5"))
        assert session.execute.await_count == 1

    async def test_snapshot_creates_plan_then_retries(self):
        plan = _make_plan("user01")
        svc = MeteringService()
        svc.ensure_user_plan = AsyncMock(return_value=plan)
        session = _mock_session(
            _MockResult(one_value=None),
            _MockResult(one_value=(plan, 0, 0, 0, Decimal("0"))),
        )

        snapshot = await svc._get_usage_summary_snapshot(session, "user01")

        assert snapshot == (plan, 0, 0, 0, Decimal("0"))
        svc.ensure_user_plan.assert_awaited_once_with(session, "user01")
        assert session.execute.await_count == 2

    async def test_compute_usage_combines_aggregate_and_boundary_rows(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        svc = MeteringService()
        session = _mock_session(
            _MockResult(one_value=(Decimal("4"), Decimal("8"))),
            _MockResult(
                scalars_list=None,
                one_value=None,
            ),
        )
        session.execute = AsyncMock(
            side_effect=[
                _MockResult(one_value=(Decimal("4"), Decimal("8"))),
                MagicMock(
                    all=MagicMock(
                        return_value=[
                            (
                                datetime(2026, 2, 28, 23, 0, 0, tzinfo=UTC),
                                datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
                                Decimal("2"),
                                Decimal("4"),
                            )
                        ]
                    )
                ),
            ]
        )

        result = await svc.get_compute_unit_hours_for_period(
            session,
            "user01",
            datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        )

        assert result == Decimal("3.7500")

    async def test_storage_usage_aggregates_released_rows_and_clips_boundary_rows(self, monkeypatch):
        monkeypatch.setattr("treadstone.metering.services.metering_service.utc_now", lambda: FIXED_NOW)
        svc = MeteringService()
        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _MockResult(value=Decimal("10")),
                MagicMock(
                    all=MagicMock(
                        return_value=[
                            (
                                5,
                                datetime(2026, 2, 28, 23, 0, 0, tzinfo=UTC),
                                datetime(2026, 3, 1, 1, 0, 0, tzinfo=UTC),
                            )
                        ]
                    )
                ),
            ]
        )

        result = await svc.get_storage_gib_hours_for_period(
            session,
            "user01",
            datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
        )

        assert result == Decimal("15.0000")


# ═══════════════════════════════════════════════════════
#  F14 — check_sandbox_duration
# ═══════════════════════════════════════════════════════


class TestCheckSandboxDuration:
    async def test_returns_max_duration_for_free_tier(self):
        plan = _make_plan("user01", max_sandbox_duration_seconds=7200)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        result = await svc.check_sandbox_duration(AsyncMock(), "user01")
        assert result == 7200

    async def test_returns_max_duration_for_pro_tier(self):
        plan = _make_plan("user01", tier="pro", max_sandbox_duration_seconds=0)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        result = await svc.check_sandbox_duration(AsyncMock(), "user01")
        assert result == 0

    async def test_returns_overridden_duration(self):
        plan = _make_plan("user01", max_sandbox_duration_seconds=14400)
        svc = MeteringService()
        svc.get_user_plan = AsyncMock(return_value=plan)

        result = await svc.check_sandbox_duration(AsyncMock(), "user01")
        assert result == 14400
