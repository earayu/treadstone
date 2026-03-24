from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now


class SandboxWebLink(Base):
    __tablename__ = "sandbox_web_link"
    __table_args__ = (UniqueConstraint("sandbox_id", name="uq_sandbox_web_link_sandbox_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: "swl" + random_id(24))
    sandbox_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("sandbox.id", ondelete="cascade"), nullable=False, index=True
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False, index=True
    )
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def is_expired(self) -> bool:
        if self.gmt_expires is None:
            return False
        expires_at = self.gmt_expires
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return utc_now() >= expires_at
