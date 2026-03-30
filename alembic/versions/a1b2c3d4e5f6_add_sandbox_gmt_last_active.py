"""add sandbox gmt_last_active

Add gmt_last_active column to sandbox table for idle-timeout tracking.
The lifecycle tick loop uses this timestamp to determine when a sandbox
has been idle longer than its auto_stop_interval.

Revision ID: a1b2c3d4e5f6
Revises: f2a3b4c5d6e7
Create Date: 2026-03-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sandbox",
        sa.Column("gmt_last_active", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sandbox", "gmt_last_active")
