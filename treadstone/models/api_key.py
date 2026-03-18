from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "key" + random_id())
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
