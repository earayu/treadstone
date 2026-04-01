"""add waitlist github_or_portfolio_url

Revision ID: 6442e2b785c9
Revises: c9d27ea3b835
Create Date: 2026-04-01 20:05:18.921787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6442e2b785c9'
down_revision: Union[str, Sequence[str], None] = 'c9d27ea3b835'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "waitlist_application",
        sa.Column("github_or_portfolio_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("waitlist_application", "github_or_portfolio_url")
