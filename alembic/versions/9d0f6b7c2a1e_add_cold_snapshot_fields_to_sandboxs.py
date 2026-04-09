"""add cold snapshot fields to sandboxes

Revision ID: 9d0f6b7c2a1e
Revises: 1eeb226c1bf3
Create Date: 2026-04-09 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d0f6b7c2a1e"
down_revision: str | Sequence[str] | None = "1eeb226c1bf3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sandbox", sa.Column("pending_operation", sa.String(length=32), nullable=True))
    op.add_column("sandbox", sa.Column("pending_operation_target_status", sa.String(length=32), nullable=True))
    op.add_column("sandbox", sa.Column("storage_backend_mode", sa.String(length=32), nullable=True))
    op.add_column("sandbox", sa.Column("k8s_workspace_pvc_name", sa.String(length=255), nullable=True))
    op.add_column("sandbox", sa.Column("k8s_workspace_pv_name", sa.String(length=255), nullable=True))
    op.add_column("sandbox", sa.Column("workspace_volume_handle", sa.String(length=255), nullable=True))
    op.add_column("sandbox", sa.Column("workspace_zone", sa.String(length=255), nullable=True))
    op.add_column("sandbox", sa.Column("snapshot_provider_id", sa.String(length=255), nullable=True))
    op.add_column("sandbox", sa.Column("snapshot_k8s_volume_snapshot_name", sa.String(length=255), nullable=True))
    op.add_column(
        "sandbox",
        sa.Column("snapshot_k8s_volume_snapshot_content_name", sa.String(length=255), nullable=True),
    )
    op.add_column("sandbox", sa.Column("gmt_snapshotted", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sandbox", sa.Column("gmt_restored", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sandbox", sa.Column("gmt_snapshot_archived", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_sandbox_pending_operation", "sandbox", ["pending_operation"], unique=False)
    op.create_index("ix_sandbox_k8s_workspace_pvc_name", "sandbox", ["k8s_workspace_pvc_name"], unique=False)
    op.create_index("ix_sandbox_k8s_workspace_pv_name", "sandbox", ["k8s_workspace_pv_name"], unique=False)
    op.create_index("ix_sandbox_snapshot_provider_id", "sandbox", ["snapshot_provider_id"], unique=False)
    op.create_index(
        "ix_sandbox_snapshot_k8s_volume_snapshot_name",
        "sandbox",
        ["snapshot_k8s_volume_snapshot_name"],
        unique=False,
    )
    op.create_index(
        "ix_sandbox_snapshot_k8s_volume_snapshot_content_name",
        "sandbox",
        ["snapshot_k8s_volume_snapshot_content_name"],
        unique=False,
    )

    op.add_column(
        "storage_ledger",
        sa.Column("backend_mode", sa.String(length=32), nullable=False, server_default="live_disk"),
    )
    op.alter_column("storage_ledger", "backend_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("storage_ledger", "backend_mode")

    op.drop_index("ix_sandbox_snapshot_k8s_volume_snapshot_content_name", table_name="sandbox")
    op.drop_index("ix_sandbox_snapshot_k8s_volume_snapshot_name", table_name="sandbox")
    op.drop_index("ix_sandbox_snapshot_provider_id", table_name="sandbox")
    op.drop_index("ix_sandbox_k8s_workspace_pv_name", table_name="sandbox")
    op.drop_index("ix_sandbox_k8s_workspace_pvc_name", table_name="sandbox")
    op.drop_index("ix_sandbox_pending_operation", table_name="sandbox")

    op.drop_column("sandbox", "gmt_snapshot_archived")
    op.drop_column("sandbox", "gmt_restored")
    op.drop_column("sandbox", "gmt_snapshotted")
    op.drop_column("sandbox", "snapshot_k8s_volume_snapshot_content_name")
    op.drop_column("sandbox", "snapshot_k8s_volume_snapshot_name")
    op.drop_column("sandbox", "snapshot_provider_id")
    op.drop_column("sandbox", "workspace_zone")
    op.drop_column("sandbox", "workspace_volume_handle")
    op.drop_column("sandbox", "k8s_workspace_pv_name")
    op.drop_column("sandbox", "k8s_workspace_pvc_name")
    op.drop_column("sandbox", "storage_backend_mode")
    op.drop_column("sandbox", "pending_operation_target_status")
    op.drop_column("sandbox", "pending_operation")
