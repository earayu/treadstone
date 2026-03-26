import hashlib
import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now

CLI_FLOW_TTL_SECONDS = 600


def hash_flow_secret(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_flow_secret() -> str:
    return secrets.token_urlsafe(32)


class CliLoginFlow(Base):
    __tablename__ = "cli_login_flow"
    __table_args__ = (Index("ix_cli_login_flow_status_expires", "status", "gmt_expires"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "clf" + random_id())
    flow_secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    user_id: Mapped[str | None] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gmt_completed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
