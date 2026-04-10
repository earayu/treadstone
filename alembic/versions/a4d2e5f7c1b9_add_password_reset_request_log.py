"""add password reset request log

Revision ID: a4d2e5f7c1b9
Revises: 4b3f2f3fd7d8
Create Date: 2026-04-10 21:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d2e5f7c1b9"
down_revision: str | Sequence[str] | None = "4b3f2f3fd7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_reset_request_log",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("requested_email", sa.String(length=320), nullable=False),
        sa.Column("matched_user_id", sa.String(length=24), nullable=True),
        sa.Column("was_sent", sa.Boolean(), nullable=False),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["matched_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_password_reset_request_log_email_created",
        "password_reset_request_log",
        ["requested_email", "gmt_created"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_request_log_ip_created",
        "password_reset_request_log",
        ["request_ip", "gmt_created"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_request_log_matched_user_id",
        "password_reset_request_log",
        ["matched_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_request_log_matched_user_id", table_name="password_reset_request_log")
    op.drop_index("ix_password_reset_request_log_ip_created", table_name="password_reset_request_log")
    op.drop_index("ix_password_reset_request_log_email_created", table_name="password_reset_request_log")
    op.drop_table("password_reset_request_log")
