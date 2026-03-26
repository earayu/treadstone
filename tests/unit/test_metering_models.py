"""Unit tests for metering models (F01) and helpers (F04)."""

from decimal import Decimal

import pytest

from treadstone.core.errors import BadRequestError
from treadstone.models.metering import (
    ComputeSession,
    CreditGrant,
    StorageLedger,
    StorageState,
    TierTemplate,
    UserPlan,
)
from treadstone.services.metering_helpers import (
    TEMPLATE_SPECS,
    ConsumeResult,
    calculate_credit_rate,
    parse_storage_size_gib,
)

# ── StorageState Enum ──


def test_storage_state_values():
    assert StorageState.ACTIVE == "active"
    assert StorageState.ARCHIVED == "archived"
    assert StorageState.DELETED == "deleted"


# ── TierTemplate ──


def test_tier_template_tablename():
    assert TierTemplate.__tablename__ == "tier_template"


def test_tier_template_fields_exist():
    tt = TierTemplate()
    for field in [
        "id",
        "tier_name",
        "compute_credits_monthly",
        "storage_credits_monthly",
        "max_concurrent_running",
        "max_sandbox_duration_seconds",
        "allowed_templates",
        "grace_period_seconds",
        "is_active",
        "gmt_created",
        "gmt_updated",
    ]:
        assert hasattr(tt, field), f"Missing field: {field}"


def test_tier_template_id_default_callable():
    col = TierTemplate.__table__.columns["id"]
    assert col.default is not None and col.default.is_callable


def test_tier_template_default_is_active():
    col_defaults = {col.name: col.default for col in TierTemplate.__table__.columns if col.default is not None}
    assert col_defaults["is_active"].arg is True


# ── UserPlan ──


def test_user_plan_tablename():
    assert UserPlan.__tablename__ == "user_plan"


def test_user_plan_fields_exist():
    plan = UserPlan()
    for field in [
        "id",
        "user_id",
        "tier",
        "compute_credits_monthly_limit",
        "storage_credits_monthly_limit",
        "max_concurrent_running",
        "max_sandbox_duration_seconds",
        "allowed_templates",
        "grace_period_seconds",
        "period_start",
        "period_end",
        "compute_credits_monthly_used",
        "overrides",
        "grace_period_started_at",
        "warning_80_notified_at",
        "warning_100_notified_at",
        "gmt_created",
        "gmt_updated",
    ]:
        assert hasattr(plan, field), f"Missing field: {field}"


def test_user_plan_id_default_callable():
    col = UserPlan.__table__.columns["id"]
    assert col.default is not None and col.default.is_callable


def test_user_plan_unique_user_constraint():
    cols = {c.name for uc in UserPlan.__table__.constraints for c in getattr(uc, "columns", [])}
    assert "user_id" in cols


# ── CreditGrant ──


def test_credit_grant_tablename():
    assert CreditGrant.__tablename__ == "credit_grant"


def test_credit_grant_fields_exist():
    cg = CreditGrant()
    for field in [
        "id",
        "user_id",
        "credit_type",
        "grant_type",
        "campaign_id",
        "original_amount",
        "remaining_amount",
        "reason",
        "granted_by",
        "granted_at",
        "expires_at",
        "gmt_created",
        "gmt_updated",
    ]:
        assert hasattr(cg, field), f"Missing field: {field}"


def test_credit_grant_id_default_callable():
    col = CreditGrant.__table__.columns["id"]
    assert col.default is not None and col.default.is_callable


def test_credit_grant_indexes():
    index_names = {idx.name for idx in CreditGrant.__table__.indexes}
    assert "ix_credit_grant_user_type" in index_names
    assert "ix_credit_grant_expires" in index_names


# ── ComputeSession ──


def test_compute_session_tablename():
    assert ComputeSession.__tablename__ == "compute_session"


def test_compute_session_fields_exist():
    cs = ComputeSession()
    for field in [
        "id",
        "sandbox_id",
        "user_id",
        "template",
        "credit_rate_per_hour",
        "started_at",
        "ended_at",
        "last_metered_at",
        "credits_consumed",
        "credits_consumed_monthly",
        "credits_consumed_extra",
        "gmt_created",
        "gmt_updated",
    ]:
        assert hasattr(cs, field), f"Missing field: {field}"


def test_compute_session_id_default_callable():
    col = ComputeSession.__table__.columns["id"]
    assert col.default is not None and col.default.is_callable


def test_compute_session_indexes():
    index_names = {idx.name for idx in ComputeSession.__table__.indexes}
    assert "ix_compute_session_open" in index_names


# ── StorageLedger ──


def test_storage_ledger_tablename():
    assert StorageLedger.__tablename__ == "storage_ledger"


def test_storage_ledger_fields_exist():
    sl = StorageLedger()
    for field in [
        "id",
        "user_id",
        "sandbox_id",
        "size_gib",
        "storage_state",
        "allocated_at",
        "released_at",
        "archived_at",
        "gib_hours_consumed",
        "last_metered_at",
        "gmt_created",
        "gmt_updated",
    ]:
        assert hasattr(sl, field), f"Missing field: {field}"


def test_storage_ledger_id_default_callable():
    col = StorageLedger.__table__.columns["id"]
    assert col.default is not None and col.default.is_callable


def test_storage_ledger_indexes():
    index_names = {idx.name for idx in StorageLedger.__table__.indexes}
    assert "ix_storage_ledger_user_state" in index_names
    assert "ix_storage_ledger_sandbox" in index_names


# ── Metering Helpers (F04) ──


class TestCalculateCreditRate:
    def test_tiny(self):
        assert calculate_credit_rate("tiny") == Decimal("0.25")

    def test_small(self):
        assert calculate_credit_rate("small") == Decimal("0.5")

    def test_medium(self):
        assert calculate_credit_rate("medium") == Decimal("1")

    def test_large(self):
        assert calculate_credit_rate("large") == Decimal("2")

    def test_xlarge(self):
        assert calculate_credit_rate("xlarge") == Decimal("4")

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError, match="Unknown template"):
            calculate_credit_rate("nonexistent")


class TestTemplateSpecs:
    def test_all_templates_present(self):
        assert set(TEMPLATE_SPECS.keys()) == {"tiny", "small", "medium", "large", "xlarge"}

    def test_ratio_is_1_to_2(self):
        for name, spec in TEMPLATE_SPECS.items():
            assert spec["memory_gib"] == spec["vcpu"] * 2, f"{name}: memory should be 2x vcpu"


class TestParseStorageSizeGib:
    def test_5gi(self):
        assert parse_storage_size_gib("5Gi") == 5

    def test_10gi(self):
        assert parse_storage_size_gib("10Gi") == 10

    def test_20gi(self):
        assert parse_storage_size_gib("20Gi") == 20

    def test_1ti(self):
        assert parse_storage_size_gib("1Ti") == 1024

    def test_invalid_suffix_raises(self):
        with pytest.raises(BadRequestError, match="Unsupported storage size format"):
            parse_storage_size_gib("100Mi")

    def test_invalid_number_raises(self):
        with pytest.raises(BadRequestError, match="Invalid storage size"):
            parse_storage_size_gib("abcGi")


class TestConsumeResult:
    def test_fields(self):
        cr = ConsumeResult(monthly=Decimal("5"), extra=Decimal("3"), shortfall=Decimal("0"))
        assert cr.monthly == Decimal("5")
        assert cr.extra == Decimal("3")
        assert cr.shortfall == Decimal("0")

    def test_frozen(self):
        cr = ConsumeResult(monthly=Decimal("5"), extra=Decimal("3"), shortfall=Decimal("0"))
        with pytest.raises(AttributeError):
            cr.monthly = Decimal("10")
