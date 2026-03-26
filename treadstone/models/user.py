import secrets
from datetime import UTC, datetime
from enum import StrEnum

from fastapi_users.db import SQLAlchemyBaseOAuthAccountTable, SQLAlchemyBaseUserTable
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession
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
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=Role.RO.value)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship("OAuthAccount", lazy="joined", back_populates="user")


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable[str], Base):
    __tablename__ = "oauth_account"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "oauth" + random_id())
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user.id", ondelete="cascade"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")


class Invitation(Base):
    __tablename__ = "invitation"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "invite" + random_id())
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=Role.RO.value)

    def is_valid(self) -> bool:
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return not self.is_used and utc_now() < expires_at

    async def use(self, session: AsyncSession) -> None:
        self.is_used = True
        self.used_at = utc_now()
        session.add(self)
