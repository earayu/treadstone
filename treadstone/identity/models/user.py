import secrets
from datetime import UTC, datetime
from enum import StrEnum

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTable, SQLAlchemyBaseUserTable
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from treadstone.core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def random_id(n: int = 16) -> str:
    return secrets.token_hex(n // 2)


class Role(StrEnum):
    ADMIN = "admin"
    RW = "rw"
    RO = "ro"


class User(SQLAlchemyBaseUserTable[str], Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "user" + random_id())
    username: Mapped[str | None] = mapped_column(String(256), unique=True, nullable=True)
    has_local_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=Role.RW.value)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship("OAuthAccount", lazy="joined", back_populates="user")


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable[str], Base):
    __tablename__ = "oauth_account"
    __table_args__ = (
        UniqueConstraint("oauth_name", "account_id", name="uq_oauth_account_provider_account"),
        UniqueConstraint("user_id", "oauth_name", name="uq_oauth_account_user_provider"),
    )

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "oauth" + random_id())
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.id", ondelete="cascade"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")
