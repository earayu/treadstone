from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.core.errors import (
    GlobalStorageCapExceededError,
    SandboxCapExceededError,
    UserRegistrationCapExceededError,
    WaitlistCapExceededError,
)
from treadstone.identity.models.user import User, utc_now
from treadstone.metering.services.metering_helpers import parse_storage_size_gib as _parse_storage_size_gib_str
from treadstone.platform.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID, PlatformLimits
from treadstone.platform.models.waitlist import WaitlistApplication
from treadstone.sandbox.models.sandbox import Sandbox

__all__ = [
    "PLATFORM_LIMITS_REFRESH_INTERVAL_SECONDS",
    "PlatformLimitsConfigSnapshot",
    "PlatformLimitsRuntime",
    "PlatformLimitsService",
    "PlatformLimitsSnapshot",
    "PlatformLimitsUsageSnapshot",
]

PLATFORM_LIMITS_REFRESH_INTERVAL_SECONDS = 15

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformLimitsConfigSnapshot:
    max_registered_users: int | None = None
    max_total_sandboxes: int | None = None
    max_total_storage_gib: int | None = None
    max_waitlist_applications: int | None = None


@dataclass(frozen=True)
class PlatformLimitsUsageSnapshot:
    registered_users: int = 0
    total_sandboxes: int = 0
    total_storage_gib: int = 0
    waitlist_applications: int = 0


@dataclass(frozen=True)
class PlatformLimitsSnapshot:
    config: PlatformLimitsConfigSnapshot
    usage: PlatformLimitsUsageSnapshot
    refreshed_at: datetime


class PlatformLimitsService:
    @staticmethod
    def _storage_size_gib_case():
        return case(
            (Sandbox.storage_size == "5Gi", 5),
            (Sandbox.storage_size == "10Gi", 10),
            (Sandbox.storage_size == "20Gi", 20),
            else_=0,
        )

    @staticmethod
    def parse_storage_size_gib(storage_size: str | None) -> int:
        if storage_size is None:
            return 0
        return _parse_storage_size_gib_str(storage_size)

    async def get_config(self, session: AsyncSession) -> PlatformLimits | None:
        return await session.get(PlatformLimits, PLATFORM_LIMITS_SINGLETON_ID)

    async def get_or_create_config(self, session: AsyncSession) -> PlatformLimits:
        config = await self.get_config(session)
        if config is None:
            config = PlatformLimits(id=PLATFORM_LIMITS_SINGLETON_ID)
            session.add(config)
            await session.flush()
        return config

    async def build_snapshot(self, session: AsyncSession) -> PlatformLimitsSnapshot:
        config = await self.get_config(session)

        registered_users = int((await session.execute(select(func.count()).select_from(User))).scalar_one())
        total_sandboxes = int(
            (
                await session.execute(select(func.count()).select_from(Sandbox).where(Sandbox.gmt_deleted.is_(None)))
            ).scalar_one()
        )
        total_storage_gib = int(
            (
                await session.execute(
                    select(func.coalesce(func.sum(self._storage_size_gib_case()), 0)).where(
                        Sandbox.gmt_deleted.is_(None),
                        Sandbox.persist.is_(True),
                    )
                )
            ).scalar_one()
        )
        waitlist_applications = int(
            (await session.execute(select(func.count()).select_from(WaitlistApplication))).scalar_one()
        )

        return PlatformLimitsSnapshot(
            config=PlatformLimitsConfigSnapshot(
                max_registered_users=config.max_registered_users if config is not None else None,
                max_total_sandboxes=config.max_total_sandboxes if config is not None else None,
                max_total_storage_gib=config.max_total_storage_gib if config is not None else None,
                max_waitlist_applications=config.max_waitlist_applications if config is not None else None,
            ),
            usage=PlatformLimitsUsageSnapshot(
                registered_users=registered_users,
                total_sandboxes=total_sandboxes,
                total_storage_gib=total_storage_gib,
                waitlist_applications=waitlist_applications,
            ),
            refreshed_at=utc_now(),
        )

    def check_user_registration_allowed(self, snapshot: PlatformLimitsSnapshot) -> None:
        maximum = snapshot.config.max_registered_users
        if maximum is not None and snapshot.usage.registered_users >= maximum:
            raise UserRegistrationCapExceededError(snapshot.usage.registered_users, maximum)

    def check_sandbox_creation_allowed(self, snapshot: PlatformLimitsSnapshot) -> None:
        maximum = snapshot.config.max_total_sandboxes
        if maximum is not None and snapshot.usage.total_sandboxes >= maximum:
            raise SandboxCapExceededError(snapshot.usage.total_sandboxes, maximum)

    def check_storage_allocation_allowed(self, snapshot: PlatformLimitsSnapshot, requested_gib: int) -> None:
        maximum = snapshot.config.max_total_storage_gib
        if maximum is not None and (snapshot.usage.total_storage_gib + requested_gib) > maximum:
            raise GlobalStorageCapExceededError(snapshot.usage.total_storage_gib, requested_gib, maximum)

    def check_waitlist_submission_allowed(self, snapshot: PlatformLimitsSnapshot) -> None:
        maximum = snapshot.config.max_waitlist_applications
        if maximum is not None and snapshot.usage.waitlist_applications >= maximum:
            raise WaitlistCapExceededError(snapshot.usage.waitlist_applications, maximum)


class PlatformLimitsRuntime:
    def __init__(
        self,
        *,
        service: PlatformLimitsService | None = None,
        refresh_interval_seconds: int = PLATFORM_LIMITS_REFRESH_INTERVAL_SECONDS,
    ) -> None:
        self._service = service or PlatformLimitsService()
        self._refresh_interval_seconds = refresh_interval_seconds
        self._snapshot: PlatformLimitsSnapshot | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._bind_token: int | None = None

    async def start(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        await self.force_refresh()
        if self._task is None:
            self._task = asyncio.create_task(self._run_refresh_loop())

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._session_factory = None
        self._snapshot = None
        self._bind_token = None

    async def _run_refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(self._refresh_interval_seconds)
            try:
                await self.force_refresh()
            except Exception:
                logger.exception("Platform limits refresh failed")

    @staticmethod
    def _session_bind_token(session: AsyncSession) -> int | None:
        bind = session.sync_session.bind
        return id(bind) if bind is not None else None

    async def ensure_snapshot(self, session: AsyncSession) -> PlatformLimitsSnapshot:
        token = self._session_bind_token(session)
        if self._snapshot is not None and self._bind_token == token:
            return self._snapshot
        return await self.refresh_from_session(session)

    async def refresh_from_session(self, session: AsyncSession) -> PlatformLimitsSnapshot:
        """Rebuild the in-process snapshot from the database (same aggregates as ``force_refresh``).

        Used by admin usage responses, tests, and any caller that needs an up-to-date snapshot
        without waiting for the periodic refresh loop. Uses the same lock as ``force_refresh``.
        """
        async with self._lock:
            token = self._session_bind_token(session)
            snapshot = await self._service.build_snapshot(session)
            self._snapshot = snapshot
            self._bind_token = token
            return snapshot

    async def force_refresh(self) -> PlatformLimitsSnapshot | None:
        if self._session_factory is None:
            return self._snapshot

        async with self._lock:
            async with self._session_factory() as session:
                snapshot = await self._service.build_snapshot(session)
                self._snapshot = snapshot
                self._bind_token = self._session_bind_token(session)
                return snapshot
