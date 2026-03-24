"""hash api keys and drop plaintext secret

Revision ID: 2b57d0d7c7d8
Revises: bc37bfeef9ac
Create Date: 2026-03-24 18:20:00.000000

"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2b57d0d7c7d8"
down_revision: Union[str, Sequence[str], None] = "bc37bfeef9ac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _build_api_key_preview(secret: str) -> str:
    return f"{secret[:7]}...{secret[-4:]}"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("api_key", sa.Column("key_hash", sa.String(length=64), nullable=True))
    op.add_column("api_key", sa.Column("key_preview", sa.String(length=16), nullable=True))

    connection = op.get_bind()
    api_key_table = sa.table(
        "api_key",
        sa.column("id", sa.String(length=24)),
        sa.column("key", sa.String(length=64)),
        sa.column("key_hash", sa.String(length=64)),
        sa.column("key_preview", sa.String(length=16)),
    )
    rows = connection.execute(sa.select(api_key_table.c.id, api_key_table.c.key)).mappings().all()
    for row in rows:
        connection.execute(
            api_key_table.update()
            .where(api_key_table.c.id == row["id"])
            .values(
                key_hash=_hash_api_key(row["key"]),
                key_preview=_build_api_key_preview(row["key"]),
            )
        )

    op.alter_column("api_key", "key_hash", nullable=False)
    op.alter_column("api_key", "key_preview", nullable=False)
    op.drop_index(op.f("ix_api_key_key"), table_name="api_key")
    op.create_index(op.f("ix_api_key_key_hash"), "api_key", ["key_hash"], unique=True)
    op.drop_column("api_key", "key")


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "Cannot downgrade this migration because plaintext API key secrets cannot be reconstructed from hashes."
    )
