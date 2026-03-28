"""split credit_grant into compute_grant and storage_quota_grant

Replaces the single credit_grant table (which overloaded consumable compute
credits and capacity-based storage quotas) with two purpose-built tables:

- compute_grant: consumable credits with remaining_amount
- storage_quota_grant: capacity entitlements with size_gib

Revision ID: d7e8f9a0b1c2
Revises: c4d5e6f7a8b9
Create Date: 2026-03-29 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "compute_grant",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("user_id", sa.String(24), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grant_type", sa.String(32), nullable=False),
        sa.Column("campaign_id", sa.String(64), nullable=True),
        sa.Column("original_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("granted_by", sa.String(24), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gmt_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compute_grant_user", "compute_grant", ["user_id"])
    op.create_index(
        "ix_compute_grant_expires",
        "compute_grant",
        ["expires_at"],
        postgresql_where=sa.text("remaining_amount > 0"),
    )

    op.create_table(
        "storage_quota_grant",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("user_id", sa.String(24), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grant_type", sa.String(32), nullable=False),
        sa.Column("campaign_id", sa.String(64), nullable=True),
        sa.Column("size_gib", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("granted_by", sa.String(24), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gmt_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_storage_quota_grant_user", "storage_quota_grant", ["user_id"])

    # Migrate existing data
    op.execute(
        sa.text("""
        INSERT INTO compute_grant
            (id, user_id, grant_type, campaign_id, original_amount, remaining_amount,
             reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated)
        SELECT id, user_id, grant_type, campaign_id, original_amount, remaining_amount,
               reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated
        FROM credit_grant
        WHERE credit_type = 'compute'
    """)
    )

    op.execute(
        sa.text("""
        INSERT INTO storage_quota_grant
            (id, user_id, grant_type, campaign_id, size_gib,
             reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated)
        SELECT
            CONCAT('sqg', SUBSTRING(id FROM 3)),
            user_id, grant_type, campaign_id, CAST(original_amount AS INTEGER),
            reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated
        FROM credit_grant
        WHERE credit_type = 'storage'
    """)
    )

    op.drop_table("credit_grant")


def downgrade() -> None:
    op.create_table(
        "credit_grant",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("user_id", sa.String(24), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credit_type", sa.String(16), nullable=False),
        sa.Column("grant_type", sa.String(32), nullable=False),
        sa.Column("campaign_id", sa.String(64), nullable=True),
        sa.Column("original_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(10, 4), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("granted_by", sa.String(24), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gmt_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_grant_user_type", "credit_grant", ["user_id", "credit_type"])
    op.create_index(
        "ix_credit_grant_expires",
        "credit_grant",
        ["expires_at"],
        postgresql_where=sa.text("remaining_amount > 0"),
    )

    op.execute(
        sa.text("""
        INSERT INTO credit_grant
            (id, user_id, credit_type, grant_type, campaign_id, original_amount, remaining_amount,
             reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated)
        SELECT id, user_id, 'compute', grant_type, campaign_id, original_amount, remaining_amount,
               reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated
        FROM compute_grant
    """)
    )

    op.execute(
        sa.text("""
        INSERT INTO credit_grant
            (id, user_id, credit_type, grant_type, campaign_id, original_amount, remaining_amount,
             reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated)
        SELECT
            CONCAT('cg', SUBSTRING(id FROM 4)),
            user_id, 'storage', grant_type, campaign_id,
            CAST(size_gib AS NUMERIC(10,4)), CAST(size_gib AS NUMERIC(10,4)),
            reason, granted_by, granted_at, expires_at, gmt_created, gmt_updated
        FROM storage_quota_grant
    """)
    )

    op.drop_table("storage_quota_grant")
    op.drop_table("compute_grant")
