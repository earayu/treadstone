from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class SandboxStatus(StrEnum):
    CREATING = "creating"
    READY = "ready"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"
    DELETED = "deleted"


VALID_TRANSITIONS: dict[str, list[str]] = {
    SandboxStatus.CREATING: [SandboxStatus.READY, SandboxStatus.ERROR],
    SandboxStatus.READY: [SandboxStatus.STOPPED, SandboxStatus.ERROR, SandboxStatus.DELETING],
    SandboxStatus.STOPPED: [SandboxStatus.READY, SandboxStatus.DELETING, SandboxStatus.DELETED],
    SandboxStatus.ERROR: [SandboxStatus.STOPPED, SandboxStatus.DELETING],
    SandboxStatus.DELETING: [SandboxStatus.DELETED],
    SandboxStatus.DELETED: [],
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class Sandbox(Base):
    __tablename__ = "sandbox"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "sb" + random_id())
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True
    )

    template: Mapped[str] = mapped_column(String(255), nullable=False)
    runtime_type: Mapped[str] = mapped_column(String(64), nullable=False, default="aio")
    image: Mapped[str] = mapped_column(String(512), nullable=False)

    labels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    auto_stop_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    auto_delete_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)

    k8s_sandbox_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    k8s_namespace: Mapped[str] = mapped_column(String(255), nullable=False, default="treadstone")
    k8s_resource_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=SandboxStatus.CREATING)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    endpoints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_stopped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
