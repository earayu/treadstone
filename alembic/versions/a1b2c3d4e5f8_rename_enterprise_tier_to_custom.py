"""Rename enterprise tier to custom and update Custom Plan defaults.

- tier key: enterprise -> custom (display: Custom Plan in UI)
- compute_units_monthly: 1000 CU-h
- storage_capacity_gib: 100
- max_concurrent_running: 50
- max_sandbox_duration_seconds: 7 days
- grace_period_seconds: 24 hours

Revision ID: a1b2c3d4e5f8
Revises: 687cfa1d22de
Create Date: 2026-03-30

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f8"
down_revision: str | Sequence[str] | None = "687cfa1d22de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MAX_SANDBOX_DURATION = 7 * 24 * 60 * 60
_GRACE_PERIOD = 24 * 60 * 60

_ALL_TEMPLATES = [
    "aio-sandbox-tiny",
    "aio-sandbox-small",
    "aio-sandbox-medium",
    "aio-sandbox-large",
    "aio-sandbox-xlarge",
]


def upgrade() -> None:
    allowed = json.dumps(_ALL_TEMPLATES)
    op.execute(
        sa.text("""
            UPDATE user_plan SET tier = 'custom', gmt_updated = NOW()
            WHERE tier = 'enterprise'
        """)
    )
    op.execute(
        sa.text(f"""
            UPDATE tier_template SET
                tier_name = 'custom',
                compute_units_monthly = 1000,
                storage_capacity_gib = 100,
                max_concurrent_running = 50,
                max_sandbox_duration_seconds = {_MAX_SANDBOX_DURATION},
                grace_period_seconds = {_GRACE_PERIOD},
                allowed_templates = '{allowed}'::json,
                gmt_updated = NOW()
            WHERE tier_name = 'enterprise'
        """)
    )


def downgrade() -> None:
    allowed = json.dumps(_ALL_TEMPLATES)
    op.execute(
        sa.text("""
            UPDATE user_plan SET tier = 'enterprise', gmt_updated = NOW()
            WHERE tier = 'custom'
        """)
    )
    op.execute(
        sa.text(f"""
            UPDATE tier_template SET
                tier_name = 'enterprise',
                compute_units_monthly = 5000,
                storage_capacity_gib = 500,
                max_concurrent_running = 50,
                max_sandbox_duration_seconds = 86400,
                grace_period_seconds = 7200,
                allowed_templates = '{allowed}'::json,
                gmt_updated = NOW()
            WHERE tier_name = 'custom'
        """)
    )
