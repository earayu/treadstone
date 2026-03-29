"""rename credits to compute units

Rename user-facing "credits" terminology to "Compute Units" (CU) to align
with Neon-style CU = max(vCPU, memory_GiB / 2) semantics.

Affected columns:
- tier_template.compute_credits_monthly  -> compute_units_monthly
- user_plan.compute_credits_monthly_limit -> compute_units_monthly_limit
- user_plan.compute_credits_monthly_used  -> compute_units_monthly_used

Values are unchanged — they already represented CU-hours via calculate_credit_rate.

Revision ID: e1a2b3c4d5f6
Revises: 351062994638
Create Date: 2026-03-29
"""

from alembic import op

revision = "e1a2b3c4d5f6"
down_revision = "351062994638"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tier_template", "compute_credits_monthly", new_column_name="compute_units_monthly")
    op.alter_column("user_plan", "compute_credits_monthly_limit", new_column_name="compute_units_monthly_limit")
    op.alter_column("user_plan", "compute_credits_monthly_used", new_column_name="compute_units_monthly_used")


def downgrade() -> None:
    op.alter_column("tier_template", "compute_units_monthly", new_column_name="compute_credits_monthly")
    op.alter_column("user_plan", "compute_units_monthly_limit", new_column_name="compute_credits_monthly_limit")
    op.alter_column("user_plan", "compute_units_monthly_used", new_column_name="compute_credits_monthly_used")
