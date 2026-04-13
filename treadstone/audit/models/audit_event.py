from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.identity.models.user import random_id, utc_now


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_target_type_target_id", "target_type", "target_id"),
        Index("ix_audit_event_action_created_at", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "aud" + random_id())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    actor_api_key_id: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    credential_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default=AuditResult.SUCCESS.value, index=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
