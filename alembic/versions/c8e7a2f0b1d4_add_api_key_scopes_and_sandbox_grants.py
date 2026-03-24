"""add api key scopes and sandbox grants

Revision ID: c8e7a2f0b1d4
Revises: 2b57d0d7c7d8
Create Date: 2026-03-24 21:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8e7a2f0b1d4"
down_revision: Union[str, Sequence[str], None] = "2b57d0d7c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_key",
        sa.Column("control_plane_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "api_key",
        sa.Column("data_plane_mode", sa.String(length=16), nullable=False, server_default="all"),
    )
    op.add_column("api_key", sa.Column("gmt_updated", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    api_key_table = sa.table(
        "api_key",
        sa.column("gmt_created", sa.DateTime(timezone=True)),
        sa.column("gmt_updated", sa.DateTime(timezone=True)),
    )
    connection.execute(
        api_key_table.update().where(api_key_table.c.gmt_updated.is_(None)).values(gmt_updated=api_key_table.c.gmt_created)
    )
    op.alter_column("api_key", "gmt_updated", nullable=False)

    op.create_table(
        "api_key_sandbox_grant",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("api_key_id", sa.String(length=24), nullable=False),
        sa.Column("sandbox_id", sa.String(length=24), nullable=False),
        sa.Column("gmt_created", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_key.id"], ondelete="cascade"),
        sa.ForeignKeyConstraint(["sandbox_id"], ["sandbox.id"], ondelete="cascade"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_id", "sandbox_id", name="uq_api_key_sandbox_grant_key_sandbox"),
    )
    op.create_index(op.f("ix_api_key_sandbox_grant_api_key_id"), "api_key_sandbox_grant", ["api_key_id"], unique=False)
    op.create_index(op.f("ix_api_key_sandbox_grant_sandbox_id"), "api_key_sandbox_grant", ["sandbox_id"], unique=False)

    op.alter_column("api_key", "control_plane_enabled", server_default=None)
    op.alter_column("api_key", "data_plane_mode", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_key_sandbox_grant_sandbox_id"), table_name="api_key_sandbox_grant")
    op.drop_index(op.f("ix_api_key_sandbox_grant_api_key_id"), table_name="api_key_sandbox_grant")
    op.drop_table("api_key_sandbox_grant")
    op.drop_column("api_key", "gmt_updated")
    op.drop_column("api_key", "data_plane_mode")
    op.drop_column("api_key", "control_plane_enabled")
