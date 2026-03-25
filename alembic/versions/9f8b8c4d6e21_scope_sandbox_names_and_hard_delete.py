"""scope sandbox names and hard delete

Revision ID: 9f8b8c4d6e21
Revises: ec1f57069933
Create Date: 2026-03-25 14:30:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f8b8c4d6e21"
down_revision: Union[str, Sequence[str], None] = "ec1f57069933"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES_TO_CLEAR = (
    "sandbox_web_link",
    "api_key_sandbox_grant",
    "api_key",
    "sandbox",
    "oauth_account",
    "invitation",
    "user",
)


def _clear_existing_data() -> None:
    connection = op.get_bind()
    for table_name in _TABLES_TO_CLEAR:
        connection.execute(sa.table(table_name).delete())



def upgrade() -> None:
    _clear_existing_data()

    op.drop_index(op.f("ix_sandbox_name"), table_name="sandbox")
    op.create_index(op.f("ix_sandbox_name"), "sandbox", ["name"], unique=False)
    op.create_unique_constraint("uq_sandbox_owner_name", "sandbox", ["owner_id", "name"])
    op.drop_column("sandbox", "gmt_deleted")



def downgrade() -> None:
    _clear_existing_data()

    op.add_column("sandbox", sa.Column("gmt_deleted", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_sandbox_owner_name", "sandbox", type_="unique")
    op.drop_index(op.f("ix_sandbox_name"), table_name="sandbox")
    op.create_index(op.f("ix_sandbox_name"), "sandbox", ["name"], unique=True)
