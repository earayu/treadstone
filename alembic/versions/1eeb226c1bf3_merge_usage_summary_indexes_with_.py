"""merge usage summary indexes with waitlist url head

Revision ID: 1eeb226c1bf3
Revises: 2e0d7f4e5e9d, 6442e2b785c9
Create Date: 2026-04-02 22:35:13.503423

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "1eeb226c1bf3"
down_revision: str | Sequence[str] | None = ("2e0d7f4e5e9d", "6442e2b785c9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
