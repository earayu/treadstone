"""remove restore only target status

Revision ID: 4b3f2f3fd7d8
Revises: 9d0f6b7c2a1e
Create Date: 2026-04-09 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4b3f2f3fd7d8"
down_revision: str | Sequence[str] | None = "9d0f6b7c2a1e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE sandbox
            SET pending_operation = NULL,
                status = 'cold',
                status_message = 'Cold restore-only operation was reset during upgrade.'
            WHERE pending_operation = 'restoring'
              AND pending_operation_target_status = 'stopped'
            """
        )
    )
    op.drop_column("sandbox", "pending_operation_target_status")


def downgrade() -> None:
    op.add_column("sandbox", sa.Column("pending_operation_target_status", sa.String(length=32), nullable=True))
