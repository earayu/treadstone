"""Unit tests for MeteringService (Layer 1: F05–F09)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from treadstone.core.errors import NotFoundError, ValidationError
from treadstone.models.metering import (
    ComputeSession,
    CreditGrant,
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
            "compute_credits_monthly": Decimal("10"),
            "storage_credits_monthly": 0,
            "max_concurrent_running": 1,
            "max_sandbox_duration_seconds": 1800,
            "allowed_templates": ["tiny", "small"],
            "grace_period_seconds": 600,
        },
        "pro": {
            "compute_credits_monthly": Decimal("100"),
            "storage_credits_monthly": 10,
            "max_concurrent_running": 3,
            "max_sandbox_duration_seconds": 7200,
            "allowed_templates": ["tiny", "small", "medium"],
            "grace_period_seconds": 1800,
        },
    }
    values = {**defaults.get(tier_name, defaults["free"]), **kwargs}
    return TierTemplate(tier_name=tier_name, **values)


def _make_plan(user_id: str = "user01", tier: str = "free", **kwargs) -> UserPlan:
    defaults = {
        "tier": tier,
        "compute_credits_monthly_limit": Decimal("10"),
        "compute_credits_monthly_used": Decimal("0"),
        "storage_credits_monthly_limit": 0,
        "max_concurrent_running": 1,
        "max_sandbox_duration_seconds": 1800,
        "allowed_templates": ["tiny", "small"],
        "grace_period_seconds": 600,
        "period_start": datetime(2026, 3, 1, 0, 0, 0, tzinfo=UTC),
        "period_end": datetime(2026, 4, 1, 0, 0, 0, tzinfo=UTC),
    }
    defaults.update(kwargs)
    return UserPlan(user_id=user_id, **defaults)


class _MockResult:
    """Minimal mock for SQLAlchemy async Result."""

    def __init__(self, value=None, scalars_list=None):
        self._value = value
        self._scalars_list = scalars_list

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        template = _make_template("free")
        session = _mock_session(
            _MockResult(value=None),  # no existing plan
            _MockResult(value=template),  # tier template lookup
        )
        svc = MeteringService()

        plan = await svc.ensure_user_plan(session, "user01", tier="free")

        assert plan.user_id == "user01"
        assert plan.tier == "free"
        assert plan.compute_credits_monthly_limit == Decimal("10")
        assert plan.period_start == datetime(2026, 3, 1, tzinfo=UTC)
        assert plan.period_end == datetime(2026, 4, 1, tzinfo=UTC)

        grants = _added_objects(session, CreditGrant)
        assert len(grants) == 1
        assert grants[0].credit_type == "compute"
        assert grants[0].grant_type == "welcome_bonus"
        assert grants[0].original_amount == WELCOME_BONUS_AMOUNT
        session.flush.assert_awaited_once()

    async def test_creates_pro_plan_without_welcome_bonus(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        template = _make_template("pro")
        session = _mock_session(
            _MockResult(value=None),
            _MockResult(value=template),
        )
        svc = MeteringService()

        plan = await svc.ensure_user_plan(session, "user01", tier="pro")

        assert plan.tier == "pro"
        assert plan.compute_credits_monthly_limit == Decimal("100")
        grants = _added_objects(session, CreditGrant)
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        old_plan = _make_plan("user01", tier="free")
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)
        session = _mock_session(
            _MockResult(value=old_plan),  # existing plan lookup
        )

        plan = await svc.update_user_tier(session, "user01", "pro")

        assert plan.tier == "pro"
        assert plan.compute_credits_monthly_limit == Decimal("100")
        assert plan.max_concurrent_running == 3
        assert plan.gmt_updated == FIXED_NOW

    async def test_applies_overrides(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        old_plan = _make_plan("user01", tier="free")
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)
        session = _mock_session(
            _MockResult(value=old_plan),  # existing plan lookup
        )

        overrides = {"compute_credits_monthly_limit": Decimal("500"), "max_concurrent_running": 10}
        plan = await svc.update_user_tier(session, "user01", "pro", overrides=overrides)

        assert plan.compute_credits_monthly_limit == Decimal("500")
        assert plan.max_concurrent_running == 10
        assert plan.overrides == overrides

    async def test_creates_with_target_tier_when_no_plan(self, monkeypatch):
        """First-time tier assignment should NOT create a free plan + bonus first."""
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        pro_template = _make_template("pro")
        svc = MeteringService()
        svc._get_tier_template = AsyncMock(return_value=pro_template)

        created_plan = _make_plan("user01", tier="pro", compute_credits_monthly_limit=Decimal("100"))
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
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
        assert plan.compute_credits_monthly_limit == Decimal("100")
        assert plan.max_concurrent_running == 3


class TestApplyOverrides:
    def test_valid_keys(self):
        plan = _make_plan()
        MeteringService._apply_overrides(plan, {"max_concurrent_running": 99})
        assert plan.max_concurrent_running == 99

    def test_invalid_key_raises(self):
        plan = _make_plan()
        with pytest.raises(ValidationError, match="Invalid override key"):
            MeteringService._apply_overrides(plan, {"bogus_field": 1})

    def test_all_allowed_keys_accepted(self):
        plan = _make_plan()
        overrides = {
            "compute_credits_monthly_limit": Decimal("999"),
            "storage_credits_monthly_limit": 999,
            "max_concurrent_running": 99,
            "max_sandbox_duration_seconds": 99999,
            "allowed_templates": ["tiny"],
            "grace_period_seconds": 9999,
        }
        MeteringService._apply_overrides(plan, overrides)
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
        assert grant.credit_type == "compute"
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_credits_monthly_limit=Decimal("100"),
            compute_credits_monthly_used=Decimal("50"),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session()

        result = await svc.consume_compute_credits(session, "user01", Decimal("10"))

        assert result.monthly == Decimal("10")
        assert result.extra == Decimal("0")
        assert result.shortfall == Decimal("0")
        assert plan.compute_credits_monthly_used == Decimal("60")

    async def test_monthly_plus_extra(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_credits_monthly_limit=Decimal("100"),
            compute_credits_monthly_used=Decimal("98"),
        )
        grant = CreditGrant(
            user_id="user01",
            credit_type="compute",
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
        assert plan.compute_credits_monthly_used == Decimal("100")
        assert grant.remaining_amount == Decimal("47")

    async def test_both_pools_exhausted_returns_shortfall(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_credits_monthly_limit=Decimal("10"),
            compute_credits_monthly_used=Decimal("10"),
        )
        svc = MeteringService()
        svc._get_user_plan_for_update = AsyncMock(return_value=plan)
        session = _mock_session(_MockResult(scalars_list=[]))

        result = await svc.consume_compute_credits(session, "user01", Decimal("5"))

        assert result.monthly == Decimal("0")
        assert result.extra == Decimal("0")
        assert result.shortfall == Decimal("5")

    async def test_extra_fifo_consumes_nearest_expiry_first(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_credits_monthly_limit=Decimal("10"),
            compute_credits_monthly_used=Decimal("10"),
        )
        grant_soon = CreditGrant(
            user_id="user01",
            credit_type="compute",
            grant_type="campaign",
            original_amount=Decimal("3"),
            remaining_amount=Decimal("3"),
            granted_at=FIXED_NOW,
            expires_at=FIXED_NOW + timedelta(days=7),
        )
        grant_later = CreditGrant(
            user_id="user01",
            credit_type="compute",
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        plan = _make_plan(
            "user01",
            compute_credits_monthly_limit=Decimal("10"),
            compute_credits_monthly_used=Decimal("12"),
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        session = _mock_session(
            _MockResult(value=None),  # no existing open session
        )
        svc = MeteringService()

        cs = await svc.open_compute_session(session, "sb01", "user01", "small")

        assert cs.sandbox_id == "sb01"
        assert cs.user_id == "user01"
        assert cs.template == "small"
        assert cs.credit_rate_per_hour == Decimal("0.5")
        assert cs.started_at == FIXED_NOW
        assert cs.last_metered_at == FIXED_NOW
        assert cs.ended_at is None
        session.flush.assert_awaited_once()

    async def test_returns_existing_open_session(self):
        """Idempotent: return existing open session instead of creating a duplicate."""
        existing = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="small",
            credit_rate_per_hour=Decimal("0.5"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
        )
        session = _mock_session(_MockResult(value=existing))
        svc = MeteringService()

        cs = await svc.open_compute_session(session, "sb01", "user01", "small")

        assert cs is existing
        session.flush.assert_not_awaited()

    async def test_unknown_template_raises(self):
        svc = MeteringService()
        session = _mock_session(_MockResult(value=None))
        with pytest.raises(ValueError, match="Unknown template"):
            await svc.open_compute_session(session, "sb01", "user01", "nonexistent")


class TestCloseComputeSession:
    async def test_no_open_session_returns_none(self):
        session = _mock_session(_MockResult(value=None))
        svc = MeteringService()

        result = await svc.close_compute_session(session, "sb01")

        assert result is None

    async def test_closes_session_and_consumes_final_credits(self, monkeypatch):
        started = datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC)
        close_time = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: close_time)

        cs = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="small",
            credit_rate_per_hour=Decimal("0.5"),
            started_at=started,
            last_metered_at=started,
            credits_consumed=Decimal("0"),
            credits_consumed_monthly=Decimal("0"),
            credits_consumed_extra=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=cs))
        svc = MeteringService()
        svc.consume_compute_credits = AsyncMock(
            return_value=ConsumeResult(monthly=Decimal("0.5"), extra=Decimal("0"), shortfall=Decimal("0"))
        )

        result = await svc.close_compute_session(session, "sb01")

        assert result is cs
        assert cs.ended_at == close_time
        assert cs.last_metered_at == close_time
        assert cs.credits_consumed == Decimal("0.5")
        assert cs.credits_consumed_monthly == Decimal("0.5")
        svc.consume_compute_credits.assert_awaited_once()

    async def test_zero_elapsed_still_closes(self, monkeypatch):
        """If last_metered_at == now, no credits are consumed but session still closes."""
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        cs = ComputeSession(
            sandbox_id="sb01",
            user_id="user01",
            template="tiny",
            credit_rate_per_hour=Decimal("0.25"),
            started_at=FIXED_NOW,
            last_metered_at=FIXED_NOW,
            credits_consumed=Decimal("0"),
            credits_consumed_monthly=Decimal("0"),
            credits_consumed_extra=Decimal("0"),
        )
        session = _mock_session(_MockResult(value=cs))
        svc = MeteringService()
        svc.consume_compute_credits = AsyncMock()

        result = await svc.close_compute_session(session, "sb01")

        assert result.ended_at == FIXED_NOW
        svc.consume_compute_credits.assert_not_awaited()


# ═══════════════════════════════════════════════════════
#  F09 — storage allocation / release
# ═══════════════════════════════════════════════════════


class TestRecordStorageAllocation:
    async def test_creates_active_ledger_entry(self, monkeypatch):
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
        session = _mock_session()
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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: release_time)

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
        monkeypatch.setattr("treadstone.services.metering_service.utc_now", lambda: FIXED_NOW)
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
