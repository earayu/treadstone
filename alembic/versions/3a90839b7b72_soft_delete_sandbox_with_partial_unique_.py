"""soft delete sandbox with partial unique index

Revision ID: 3a90839b7b72
Revises: e1a2b3c4d5f6
Create Date: 2026-03-29 23:25:31.141145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a90839b7b72'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sandbox", sa.Column("gmt_deleted", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_sandbox_owner_name", "sandbox", type_="unique")
    op.create_index(
        "uq_sandbox_owner_name_active",
        "sandbox",
        ["owner_id", "name"],
        unique=True,
        postgresql_where=sa.text("gmt_deleted IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sandbox_owner_name_active", table_name="sandbox", postgresql_where=sa.text("gmt_deleted IS NULL"))
    op.create_unique_constraint("uq_sandbox_owner_name", "sandbox", ["owner_id", "name"])
    op.drop_column("sandbox", "gmt_deleted")
