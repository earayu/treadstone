from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from treadstone.core.database import Base
from treadstone.identity.models.user import random_id, utc_now


class SandboxStatus(StrEnum):
    CREATING = "creating"
    READY = "ready"
    STOPPED = "stopped"
    COLD = "cold"
    ERROR = "error"
    DELETING = "deleting"
    DELETED = "deleted"


class SandboxPendingOperation(StrEnum):
    SNAPSHOTTING = "snapshotting"
    RESTORING = "restoring"


class StorageBackendMode(StrEnum):
    LIVE_DISK = "live_disk"
    STANDARD_SNAPSHOT = "standard_snapshot"
    ARCHIVE_SNAPSHOT = "archive_snapshot"


VALID_TRANSITIONS: dict[str, list[str]] = {
    SandboxStatus.CREATING: [SandboxStatus.READY, SandboxStatus.ERROR, SandboxStatus.STOPPED, SandboxStatus.DELETING],
    SandboxStatus.READY: [SandboxStatus.STOPPED, SandboxStatus.ERROR, SandboxStatus.DELETING],
    # STOPPED→ERROR: reconcile/watch mirrors K8s when CR reports ReconcilerError (DB may lag STOPPED).
    SandboxStatus.STOPPED: [
        SandboxStatus.CREATING,
        SandboxStatus.READY,
        SandboxStatus.COLD,
        SandboxStatus.ERROR,
        SandboxStatus.DELETING,
    ],
    SandboxStatus.COLD: [SandboxStatus.STOPPED, SandboxStatus.READY, SandboxStatus.ERROR, SandboxStatus.DELETING],
    SandboxStatus.ERROR: [
        SandboxStatus.READY,
        SandboxStatus.CREATING,
        SandboxStatus.STOPPED,
        SandboxStatus.COLD,
        SandboxStatus.DELETING,
    ],
    SandboxStatus.DELETING: [SandboxStatus.DELETED],
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Sandbox(Base):
    __tablename__ = "sandbox"
    __table_args__ = (
        Index(
            "uq_sandbox_owner_name_active",
            "owner_id",
            "name",
            unique=True,
            postgresql_where=text("gmt_deleted IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "sb" + random_id())
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True
    )

    template: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="aio")
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_stop_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auto_delete_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    # "claim" = SandboxClaim path (ephemeral, WarmPool-eligible)
    # "direct" = direct Sandbox CR (persistent storage)
    provision_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="claim")
    persist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_size: Mapped[str | None] = mapped_column(String(32), nullable=True)

    k8s_sandbox_claim_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    k8s_sandbox_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    k8s_namespace: Mapped[str] = mapped_column(String(255), nullable=False)
    k8s_resource_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SandboxStatus.CREATING, index=True)
    pending_operation: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    storage_backend_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)

    k8s_workspace_pvc_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    k8s_workspace_pv_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    workspace_volume_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_zone: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    snapshot_k8s_volume_snapshot_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    snapshot_k8s_volume_snapshot_content_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_stopped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_snapshotted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_restored: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_snapshot_archived: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
