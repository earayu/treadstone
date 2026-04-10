"""refresh default tier limits for long-running workloads

Revision ID: 2b7c4d9e1f6a
Revises: 8d53041b011f
Create Date: 2026-04-10 20:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b7c4d9e1f6a"
down_revision: str | Sequence[str] | None = "8d53041b011f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_tier_template = sa.table(
    "tier_template",
    sa.column("tier_name", sa.String(length=16)),
    sa.column("compute_units_monthly", sa.Numeric(10, 4)),
    sa.column("storage_capacity_gib", sa.Integer()),
    sa.column("max_concurrent_running", sa.Integer()),
    sa.column("max_sandbox_duration_seconds", sa.Integer()),
    sa.column("grace_period_seconds", sa.Integer()),
)


def upgrade() -> None:
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "free")
        .values(
            compute_units_monthly=10,
            storage_capacity_gib=0,
            max_concurrent_running=1,
            max_sandbox_duration_seconds=7200,
            grace_period_seconds=900,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "pro")
        .values(
            compute_units_monthly=180,
            storage_capacity_gib=20,
            max_concurrent_running=5,
            max_sandbox_duration_seconds=0,
            grace_period_seconds=7200,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "ultra")
        .values(
            compute_units_monthly=480,
            storage_capacity_gib=60,
            max_concurrent_running=15,
            max_sandbox_duration_seconds=0,
            grace_period_seconds=21600,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "custom")
        .values(
            compute_units_monthly=1800,
            storage_capacity_gib=200,
            max_concurrent_running=50,
            max_sandbox_duration_seconds=0,
            grace_period_seconds=86400,
        )
    )


def downgrade() -> None:
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "free")
        .values(
            compute_units_monthly=10,
            storage_capacity_gib=0,
            max_concurrent_running=1,
            max_sandbox_duration_seconds=7200,
            grace_period_seconds=900,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "pro")
        .values(
            compute_units_monthly=80,
            storage_capacity_gib=10,
            max_concurrent_running=3,
            max_sandbox_duration_seconds=28800,
            grace_period_seconds=3600,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "ultra")
        .values(
            compute_units_monthly=240,
            storage_capacity_gib=30,
            max_concurrent_running=5,
            max_sandbox_duration_seconds=86400,
            grace_period_seconds=10800,
        )
    )
    op.execute(
        _tier_template.update()
        .where(_tier_template.c.tier_name == "custom")
        .values(
            compute_units_monthly=800,
            storage_capacity_gib=100,
            max_concurrent_running=10,
            max_sandbox_duration_seconds=259200,
            grace_period_seconds=43200,
        )
    )
