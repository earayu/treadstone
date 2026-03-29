"""metering audit fixes

Add partial unique index on compute_session to prevent duplicate open sessions
for the same sandbox (BUG-1), and add compute_units_overage column to user_plan
to persist grace-period overage for absolute cap enforcement (BUG-3).

Revision ID: f2a3b4c5d6e7
Revises: e1a2b3c4d5f6
Create Date: 2026-03-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1a2b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BUG-1: partial unique index — at most one open session per sandbox
    op.create_index(
        "uq_compute_session_sandbox_active",
        "compute_session",
        ["sandbox_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )

    # BUG-3: persist overage for absolute cap enforcement during grace period
    op.add_column(
        "user_plan",
        sa.Column("compute_units_overage", sa.Numeric(10, 4), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_plan", "compute_units_overage")
    op.drop_index("uq_compute_session_sandbox_active", table_name="compute_session")
