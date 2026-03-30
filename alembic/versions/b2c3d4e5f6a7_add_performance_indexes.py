"""add performance indexes

Add indexes to frequently queried columns that were missing coverage:
- sandbox.status: background tasks filter by status every 60s
- sandbox.k8s_sandbox_name: Watch event handler queries with OR on both
  k8s_sandbox_name and k8s_sandbox_claim_name (which already has an index)
- user_plan.period_end: monthly reset tick queries WHERE period_end <= now
- compute_grant(user_id, expires_at) WHERE remaining_amount > 0: covers the
  credit consumption FIFO query pattern

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_sandbox_status", "sandbox", ["status"])
    op.create_index("ix_sandbox_k8s_sandbox_name", "sandbox", ["k8s_sandbox_name"])
    op.create_index("ix_user_plan_period_end", "user_plan", ["period_end"])
    op.create_index(
        "ix_compute_grant_user_expires_active",
        "compute_grant",
        ["user_id", "expires_at"],
        postgresql_where="remaining_amount > 0",
    )


def downgrade() -> None:
    op.drop_index("ix_compute_grant_user_expires_active", "compute_grant")
    op.drop_index("ix_user_plan_period_end", "user_plan")
    op.drop_index("ix_sandbox_k8s_sandbox_name", "sandbox")
    op.drop_index("ix_sandbox_status", "sandbox")
