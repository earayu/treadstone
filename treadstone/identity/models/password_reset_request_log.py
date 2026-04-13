from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.identity.models.user import random_id, utc_now

__all__ = [
    "PasswordResetRequestLog",
]


class PasswordResetRequestLog(Base):
    __tablename__ = "password_reset_request_log"
    __table_args__ = (
        Index("ix_password_reset_request_log_email_created", "requested_email", "gmt_created"),
        Index("ix_password_reset_request_log_ip_created", "request_ip", "gmt_created"),
        Index("ix_password_reset_request_log_matched_user_id", "matched_user_id"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "prl" + random_id())
    requested_email: Mapped[str] = mapped_column(String(320), nullable=False)
    matched_user_id: Mapped[str | None] = mapped_column(
        String(24),
        ForeignKey("user.id", ondelete="set null"),
        nullable=True,
    )
    was_sent: Mapped[bool] = mapped_column(nullable=False, default=False)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
