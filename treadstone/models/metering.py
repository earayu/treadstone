from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class StorageState(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class TierTemplate(Base):
    __tablename__ = "tier_template"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "tt" + random_id())
    tier_name: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    compute_units_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    storage_capacity_gib: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_running: Mapped[int] = mapped_column(Integer, nullable=False)
    max_sandbox_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_templates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    grace_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class UserPlan(Base):
    __tablename__ = "user_plan"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "plan" + random_id())
    user_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    tier: Mapped[str] = mapped_column(String(16), nullable=False)

    # Entitlements (copied from TierTemplate, can be overridden)
    compute_units_monthly_limit: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    storage_capacity_limit_gib: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrent_running: Mapped[int] = mapped_column(Integer, nullable=False)
    max_sandbox_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_templates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    grace_period_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    # Current period state
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    compute_units_monthly_used: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    compute_units_overage: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))

    # Admin overrides
    overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Grace Period tracking
    grace_period_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Notification dedup
    warning_80_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    warning_100_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ComputeGrant(Base):
    """Consumable compute credit grant — remaining_amount decreases over time."""

    __tablename__ = "compute_grant"
    __table_args__ = (
        Index("ix_compute_grant_user", "user_id"),
        Index(
            "ix_compute_grant_expires",
            "expires_at",
            postgresql_where=text("remaining_amount > 0"),
        ),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "cg" + random_id())
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    grant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class StorageQuotaGrant(Base):
    """Storage capacity addon — size_gib raises the user's quota ceiling."""

    __tablename__ = "storage_quota_grant"
    __table_args__ = (Index("ix_storage_quota_grant_user", "user_id"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "sqg" + random_id())
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    grant_type: Mapped[str] = mapped_column(String(32), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_gib: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by: Mapped[str | None] = mapped_column(String(24), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ComputeSession(Base):
    __tablename__ = "compute_session"
    __table_args__ = (
        Index("ix_compute_session_open", "ended_at", postgresql_where=text("ended_at IS NULL")),
        Index(
            "uq_compute_session_sandbox_active",
            "sandbox_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "cs" + random_id())
    sandbox_id: Mapped[str] = mapped_column(String(24), ForeignKey("sandbox.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id"), nullable=False, index=True)
    template: Mapped[str] = mapped_column(String(255), nullable=False)

    # Raw resource spec locked at session open time
    vcpu_request: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    memory_gib_request: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_metered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Accumulated raw resource-hours
    vcpu_hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    memory_gib_hours: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))

    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class StorageLedger(Base):
    __tablename__ = "storage_ledger"
    __table_args__ = (
        Index("ix_storage_ledger_user_state", "user_id", "storage_state"),
        Index("ix_storage_ledger_sandbox", "sandbox_id"),
        Index(
            "ix_storage_ledger_sandbox_active",
            "sandbox_id",
            unique=True,
            postgresql_where=text("storage_state = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "sl" + random_id())
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    sandbox_id: Mapped[str | None] = mapped_column(
        String(24), ForeignKey("sandbox.id", ondelete="SET NULL"), nullable=True
    )
    size_gib: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_state: Mapped[str] = mapped_column(String(16), nullable=False, default=StorageState.ACTIVE)
    allocated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gib_hours_consumed: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=Decimal("0"))
    last_metered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
