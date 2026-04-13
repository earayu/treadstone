from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.identity.models.user import utc_now

__all__ = [
    "PLATFORM_LIMITS_SINGLETON_ID",
    "PlatformLimits",
]

PLATFORM_LIMITS_SINGLETON_ID = "platform_limits"


class PlatformLimits(Base):
    __tablename__ = "platform_limits"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=PLATFORM_LIMITS_SINGLETON_ID)
    max_registered_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_total_sandboxes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_total_storage_gib: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_waitlist_applications: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
