import hashlib
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


def hash_api_key_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def build_api_key_preview(secret: str) -> str:
    return f"{secret[:7]}...{secret[-4:]}"


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "key" + random_id())
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_preview: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_expired(self) -> bool:
        if self.gmt_expires is None:
            return False
        return utc_now() >= self.gmt_expires
