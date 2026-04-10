"""add platform limits table

Revision ID: 0d5c9f8a7b6e
Revises: 4b3f2f3fd7d8
Create Date: 2026-04-10 10:30:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d5c9f8a7b6e"
down_revision: str | Sequence[str] | None = "4b3f2f3fd7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_limits",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("max_registered_users", sa.Integer(), nullable=True),
        sa.Column("max_total_sandboxes", sa.Integer(), nullable=True),
        sa.Column("max_total_storage_gib", sa.Integer(), nullable=True),
        sa.Column("max_waitlist_applications", sa.Integer(), nullable=True),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gmt_updated", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    platform_limits = sa.table(
        "platform_limits",
        sa.column("id", sa.String(length=24)),
        sa.column("max_registered_users", sa.Integer()),
        sa.column("max_total_sandboxes", sa.Integer()),
        sa.column("max_total_storage_gib", sa.Integer()),
        sa.column("max_waitlist_applications", sa.Integer()),
        sa.column("gmt_created", sa.DateTime(timezone=True)),
        sa.column("gmt_updated", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        platform_limits,
        [
            {
                "id": "platform_limits",
                "max_registered_users": None,
                "max_total_sandboxes": None,
                "max_total_storage_gib": None,
                "max_waitlist_applications": None,
                "gmt_created": now,
                "gmt_updated": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("platform_limits")
