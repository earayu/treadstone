"""update_tier_template_defaults

Update tier template defaults to new pricing tiers:
- free:  20 CU-h/mo, 0 GiB,  3 concurrent, 2 hr  auto-stop, 15 min grace
- pro:  120 CU-h/mo, 15 GiB, 8 concurrent, 24 hr auto-stop,  2 hr grace
- ultra: 400 CU-h/mo, 50 GiB, 20 concurrent, 72 hr auto-stop,  6 hr grace

Revision ID: 687cfa1d22de
Revises: b2c3d4e5f6a7
Create Date: 2026-03-30 17:55:22.382790

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "687cfa1d22de"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPGRADE_STMTS = [
    # free: 20 CU-h, 0 GiB, 3 concurrent, 7200 s (2 hr) auto-stop, 900 s (15 min) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 20,
            storage_capacity_gib         = 0,
            max_concurrent_running       = 3,
            max_sandbox_duration_seconds = 7200,
            allowed_templates            = '["aio-sandbox-tiny"]',
            grace_period_seconds         = 900,
            gmt_updated                  = NOW()
        WHERE tier_name = 'free'
    """),
    # pro: 120 CU-h, 15 GiB, 8 concurrent, 86400 s (24 hr) auto-stop, 7200 s (2 hr) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 120,
            storage_capacity_gib         = 15,
            max_concurrent_running       = 8,
            max_sandbox_duration_seconds = 86400,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium"]',
            grace_period_seconds         = 7200,
            gmt_updated                  = NOW()
        WHERE tier_name = 'pro'
    """),
    # ultra: 400 CU-h, 50 GiB, 20 concurrent, 259200 s (72 hr) auto-stop, 21600 s (6 hr) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 400,
            storage_capacity_gib         = 50,
            max_concurrent_running       = 20,
            max_sandbox_duration_seconds = 259200,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium","aio-sandbox-large","aio-sandbox-xlarge"]',
            grace_period_seconds         = 21600,
            gmt_updated                  = NOW()
        WHERE tier_name = 'ultra'
    """),
]

# Restore previous values on downgrade (original seed data from 9f3a6a152a5c)
_DOWNGRADE_STMTS = [
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 10,
            storage_capacity_gib         = 0,
            max_concurrent_running       = 1,
            max_sandbox_duration_seconds = 1800,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small"]',
            grace_period_seconds         = 600,
            gmt_updated                  = NOW()
        WHERE tier_name = 'free'
    """),
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 100,
            storage_capacity_gib         = 10,
            max_concurrent_running       = 3,
            max_sandbox_duration_seconds = 7200,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium"]',
            grace_period_seconds         = 1800,
            gmt_updated                  = NOW()
        WHERE tier_name = 'pro'
    """),
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 300,
            storage_capacity_gib         = 20,
            max_concurrent_running       = 5,
            max_sandbox_duration_seconds = 28800,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium","aio-sandbox-large"]',
            grace_period_seconds         = 3600,
            gmt_updated                  = NOW()
        WHERE tier_name = 'ultra'
    """),
]


def upgrade() -> None:
    """Update tier template values to new pricing tiers."""
    for stmt in _UPGRADE_STMTS:
        op.execute(stmt)


def downgrade() -> None:
    """Restore original seed values for tier templates."""
    for stmt in _DOWNGRADE_STMTS:
        op.execute(stmt)
