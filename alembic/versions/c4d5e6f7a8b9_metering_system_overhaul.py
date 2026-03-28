"""metering system overhaul

Rename storage columns, widen compute_session.template, add storage ledger
unique index, replace credit columns with raw resource columns.

Changes:
- tier_template: storage_credits_monthly → storage_capacity_gib
- user_plan: storage_credits_monthly_limit → storage_capacity_limit_gib
- compute_session: template String(32) → String(255)
- compute_session: drop credit_rate_per_hour, credits_consumed, credits_consumed_monthly, credits_consumed_extra
- compute_session: add vcpu_request, memory_gib_request, vcpu_hours, memory_gib_hours
- storage_ledger: add partial unique index on (sandbox_id) WHERE storage_state='active'

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-03-29 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("tier_template", "storage_credits_monthly", new_column_name="storage_capacity_gib")
    op.alter_column("user_plan", "storage_credits_monthly_limit", new_column_name="storage_capacity_limit_gib")

    op.alter_column(
        "compute_session",
        "template",
        existing_type=sa.String(32),
        type_=sa.String(255),
        existing_nullable=False,
    )

    # Replace credit columns with raw resource columns
    op.drop_column("compute_session", "credit_rate_per_hour")
    op.drop_column("compute_session", "credits_consumed")
    op.drop_column("compute_session", "credits_consumed_monthly")
    op.drop_column("compute_session", "credits_consumed_extra")

    op.add_column(
        "compute_session",
        sa.Column("vcpu_request", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("memory_gib_request", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("vcpu_hours", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("memory_gib_hours", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )

    op.create_index(
        "ix_storage_ledger_sandbox_active",
        "storage_ledger",
        ["sandbox_id"],
        unique=True,
        postgresql_where=sa.text("storage_state = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("ix_storage_ledger_sandbox_active", table_name="storage_ledger")

    op.drop_column("compute_session", "memory_gib_hours")
    op.drop_column("compute_session", "vcpu_hours")
    op.drop_column("compute_session", "memory_gib_request")
    op.drop_column("compute_session", "vcpu_request")

    op.add_column(
        "compute_session",
        sa.Column("credits_consumed_extra", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("credits_consumed_monthly", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("credits_consumed", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )
    op.add_column(
        "compute_session",
        sa.Column("credit_rate_per_hour", sa.Numeric(precision=10, scale=4), nullable=False, server_default="0"),
    )

    op.alter_column(
        "compute_session",
        "template",
        existing_type=sa.String(255),
        type_=sa.String(32),
        existing_nullable=False,
    )

    op.alter_column("user_plan", "storage_capacity_limit_gib", new_column_name="storage_credits_monthly_limit")
    op.alter_column("tier_template", "storage_capacity_gib", new_column_name="storage_credits_monthly")
