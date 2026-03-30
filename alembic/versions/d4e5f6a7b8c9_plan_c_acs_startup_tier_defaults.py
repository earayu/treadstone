"""Plan C: ACS startup tier defaults

Update tier_template defaults for ACS cold-start phase:
- free:   10 CU-h/mo,   0 GiB,  1 concurrent, 2 hr max,     tiny only,              15 min grace
- pro:    80 CU-h/mo,  10 GiB,  3 concurrent, 8 hr max,     tiny+small+medium,       1 hr grace
- ultra: 240 CU-h/mo,  30 GiB,  5 concurrent, 24 hr max,    tiny+small+medium,       3 hr grace
- custom: 800 CU-h/mo, 100 GiB, 10 concurrent, 72 hr max,   all templates,          12 hr grace

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UPGRADE_STMTS = [
    # free: 10 CU-h, 0 GiB, 1 concurrent, 7200 s (2 hr), tiny only, 900 s (15 min) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 10,
            storage_capacity_gib         = 0,
            max_concurrent_running       = 1,
            max_sandbox_duration_seconds = 7200,
            allowed_templates            = '["aio-sandbox-tiny"]',
            grace_period_seconds         = 900,
            gmt_updated                  = NOW()
        WHERE tier_name = 'free'
    """),
    # pro: 80 CU-h, 10 GiB, 3 concurrent, 28800 s (8 hr), tiny+small+medium, 3600 s (1 hr) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 80,
            storage_capacity_gib         = 10,
            max_concurrent_running       = 3,
            max_sandbox_duration_seconds = 28800,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium"]',
            grace_period_seconds         = 3600,
            gmt_updated                  = NOW()
        WHERE tier_name = 'pro'
    """),
    # ultra: 240 CU-h, 30 GiB, 5 concurrent, 86400 s (24 hr), tiny+small+medium, 10800 s (3 hr) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 240,
            storage_capacity_gib         = 30,
            max_concurrent_running       = 5,
            max_sandbox_duration_seconds = 86400,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium"]',
            grace_period_seconds         = 10800,
            gmt_updated                  = NOW()
        WHERE tier_name = 'ultra'
    """),
    # custom: 800 CU-h, 100 GiB, 10 concurrent, 259200 s (72 hr), all templates, 43200 s (12 hr) grace
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 800,
            storage_capacity_gib         = 100,
            max_concurrent_running       = 10,
            max_sandbox_duration_seconds = 259200,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium","aio-sandbox-large","aio-sandbox-xlarge"]',
            grace_period_seconds         = 43200,
            gmt_updated                  = NOW()
        WHERE tier_name = 'custom'
    """),
]

_DOWNGRADE_STMTS = [
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
    sa.text("""
        UPDATE tier_template SET
            compute_units_monthly        = 1000,
            storage_capacity_gib         = 100,
            max_concurrent_running       = 50,
            max_sandbox_duration_seconds = 604800,
            allowed_templates            = '["aio-sandbox-tiny","aio-sandbox-small","aio-sandbox-medium","aio-sandbox-large","aio-sandbox-xlarge"]',
            grace_period_seconds         = 86400,
            gmt_updated                  = NOW()
        WHERE tier_name = 'custom'
    """),
]


def upgrade() -> None:
    for stmt in _UPGRADE_STMTS:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DOWNGRADE_STMTS:
        op.execute(stmt)
