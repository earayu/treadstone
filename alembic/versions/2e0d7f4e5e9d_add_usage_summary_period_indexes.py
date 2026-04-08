"""add usage summary period indexes

Revision ID: 2e0d7f4e5e9d
Revises: c9d27ea3b835
Create Date: 2026-04-02 16:58:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e0d7f4e5e9d"
down_revision: str | Sequence[str] | None = "c9d27ea3b835"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "ix_compute_session_user_period",
        "compute_session",
        ["user_id", "started_at", "ended_at"],
        unique=False,
    )
    op.create_index(
        "ix_storage_ledger_user_period",
        "storage_ledger",
        ["user_id", "allocated_at", "released_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_storage_ledger_user_period", table_name="storage_ledger")
    op.drop_index("ix_compute_session_user_period", table_name="compute_session")
