from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class ApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WaitlistApplication(Base):
    __tablename__ = "waitlist_application"
    __table_args__ = (
        Index("ix_waitlist_application_email", "email"),
        Index("ix_waitlist_application_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "wl" + random_id())
    email: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    target_tier: Mapped[str] = mapped_column(String(16), nullable=False)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    use_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(24), ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=ApplicationStatus.PENDING)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
