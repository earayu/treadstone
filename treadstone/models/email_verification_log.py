from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class EmailVerificationLog(Base):
    __tablename__ = "email_verification_log"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "evl" + random_id())
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    verify_url: Mapped[str] = mapped_column(Text, nullable=False)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
