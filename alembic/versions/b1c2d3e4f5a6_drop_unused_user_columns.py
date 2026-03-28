"""drop unused user columns is_staff and gmt_deleted

Revision ID: b1c2d3e4f5a6
Revises: 90759a4d649a
Create Date: 2026-03-28 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "90759a4d649a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user", "is_staff")
    op.drop_column("user", "gmt_deleted")


def downgrade() -> None:
    op.add_column("user", sa.Column("gmt_deleted", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user", sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.text("false")))
