"""add user_feedback table

Revision ID: c3d4e5f6a7b8
Revises: 28823e70456d
Create Date: 2026-03-31

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "28823e70456d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.String(length=24), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_feedback_user_id", "user_feedback", ["user_id"], unique=False)
    op.create_index("ix_user_feedback_gmt_created", "user_feedback", ["gmt_created"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_feedback_gmt_created", table_name="user_feedback")
    op.drop_index("ix_user_feedback_user_id", table_name="user_feedback")
    op.drop_table("user_feedback")
