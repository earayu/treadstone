from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from treadstone.core.database import Base
from treadstone.models.user import random_id, utc_now

if TYPE_CHECKING:
    from treadstone.models.user import User


def hash_api_key_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def build_api_key_preview(secret: str) -> str:
    return f"{secret[:7]}...{secret[-4:]}"


class ApiKeyDataPlaneMode(StrEnum):
    NONE = "none"
    ALL = "all"
    SELECTED = "selected"


class ApiKey(Base):
    __tablename__ = "api_key"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "key" + random_id())
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_preview: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="default")
    user_id: Mapped[str] = mapped_column(String(24), ForeignKey("user.id", ondelete="cascade"), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    control_plane_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    data_plane_mode: Mapped[str] = mapped_column(String(16), nullable=False, default=ApiKeyDataPlaneMode.ALL.value)
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    gmt_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmt_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship("User")
    sandbox_grants: Mapped[list[ApiKeySandboxGrant]] = relationship(
        "ApiKeySandboxGrant",
        back_populates="api_key",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ApiKeySandboxGrant.gmt_created",
    )

    def is_expired(self) -> bool:
        if self.gmt_expires is None:
            return False
        expires_at = self.gmt_expires
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return utc_now() >= expires_at


class ApiKeySandboxGrant(Base):
    __tablename__ = "api_key_sandbox_grant"
    __table_args__ = (UniqueConstraint("api_key_id", "sandbox_id", name="uq_api_key_sandbox_grant_key_sandbox"),)

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=lambda: "akg" + random_id())
    api_key_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("api_key.id", ondelete="cascade"), nullable=False, index=True
    )
    sandbox_id: Mapped[str] = mapped_column(
        String(24), ForeignKey("sandbox.id", ondelete="cascade"), nullable=False, index=True
    )
    gmt_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    api_key: Mapped[ApiKey] = relationship("ApiKey", back_populates="sandbox_grants")
