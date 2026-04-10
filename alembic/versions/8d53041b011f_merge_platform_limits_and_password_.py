"""merge platform_limits and password_reset heads

Revision ID: 8d53041b011f
Revises: 0d5c9f8a7b6e, a4d2e5f7c1b9
Create Date: 2026-04-10 15:55:34.913859

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "8d53041b011f"
down_revision: str | Sequence[str] | None = ("0d5c9f8a7b6e", "a4d2e5f7c1b9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
