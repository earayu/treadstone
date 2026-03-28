"""add has_local_password to user

Revision ID: a5f9b2c17d61
Revises: f7a1b3c5d9e2
Create Date: 2026-03-28 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5f9b2c17d61"
down_revision: Union[str, Sequence[str], None] = "f7a1b3c5d9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("has_local_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            """
            UPDATE "user" AS u
            SET has_local_password = TRUE
            WHERE NOT EXISTS (
                SELECT 1
                FROM oauth_account AS oa
                WHERE oa.user_id = u.id
            )
            OR EXISTS (
                SELECT 1
                FROM audit_event AS ae
                WHERE ae.action = 'auth.register'
                  AND ae.target_type = 'user'
                  AND ae.target_id = u.id
                  AND COALESCE(ae.metadata ->> 'provider', '') = ''
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("user", "has_local_password")
