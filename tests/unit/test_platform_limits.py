from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base
from treadstone.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID, PlatformLimits
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User, utc_now
from treadstone.models.waitlist import ApplicationStatus, WaitlistApplication
from treadstone.services.platform_limits import PlatformLimitsRuntime, PlatformLimitsService


async def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_build_snapshot_without_config_row_is_unlimited():
    session_factory = await _make_session_factory()
    service = PlatformLimitsService()

    async with session_factory() as session:
        snapshot = await service.build_snapshot(session)

    assert snapshot.config.max_registered_users is None
    assert snapshot.config.max_total_sandboxes is None
    assert snapshot.config.max_total_storage_gib is None
    assert snapshot.config.max_waitlist_applications is None
    assert snapshot.usage.registered_users == 0
    assert snapshot.usage.total_sandboxes == 0
    assert snapshot.usage.total_storage_gib == 0
    assert snapshot.usage.waitlist_applications == 0


@pytest.mark.asyncio
async def test_build_snapshot_counts_usage_from_models():
    session_factory = await _make_session_factory()
    service = PlatformLimitsService()

    async with session_factory() as session:
        session.add(
            PlatformLimits(
                id=PLATFORM_LIMITS_SINGLETON_ID,
                max_registered_users=10,
                max_total_sandboxes=20,
                max_total_storage_gib=30,
                max_waitlist_applications=40,
            )
        )
        user = User(
            email="usage@example.com",
            hashed_password="hashed",
            has_local_password=True,
            is_active=True,
            is_verified=True,
            role="rw",
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                Sandbox(
                    id="sb_active_001",
                    name="active-sb",
                    owner_id=user.id,
                    template="aio-sandbox-tiny",
                    labels={},
                    endpoints={},
                    status="creating",
                    version=1,
                    k8s_namespace="default",
                    gmt_created=utc_now(),
                    gmt_last_active=utc_now(),
                    persist=True,
                    storage_size="10Gi",
                ),
                Sandbox(
                    id="sb_deleted_01",
                    name="deleted-sb",
                    owner_id=user.id,
                    template="aio-sandbox-tiny",
                    labels={},
                    endpoints={},
                    status="deleted",
                    version=1,
                    k8s_namespace="default",
                    gmt_created=utc_now(),
                    gmt_last_active=utc_now(),
                    persist=True,
                    storage_size="20Gi",
                    gmt_deleted=utc_now(),
                ),
                WaitlistApplication(
                    email="waitlist@example.com",
                    name="Waitlist User",
                    target_tier="pro",
                    status=ApplicationStatus.PENDING,
                ),
            ]
        )
        await session.commit()

    async with session_factory() as session:
        snapshot = await service.build_snapshot(session)

    assert snapshot.config.max_registered_users == 10
    assert snapshot.config.max_total_sandboxes == 20
    assert snapshot.config.max_total_storage_gib == 30
    assert snapshot.config.max_waitlist_applications == 40
    assert snapshot.usage.registered_users == 1
    assert snapshot.usage.total_sandboxes == 1
    assert snapshot.usage.total_storage_gib == 10
    assert snapshot.usage.waitlist_applications == 1


@pytest.mark.asyncio
async def test_runtime_apply_local_delta_updates_snapshot_counts():
    session_factory = await _make_session_factory()
    runtime = PlatformLimitsRuntime()

    async with session_factory() as session:
        snapshot = await runtime.ensure_snapshot(session)

    assert snapshot.usage.registered_users == 0

    await runtime.apply_local_delta(users=1, sandboxes=2, storage_gib=5, waitlist_applications=3)

    assert runtime.snapshot is not None
    assert runtime.snapshot.usage.registered_users == 1
    assert runtime.snapshot.usage.total_sandboxes == 2
    assert runtime.snapshot.usage.total_storage_gib == 5
    assert runtime.snapshot.usage.waitlist_applications == 3


@pytest.mark.asyncio
async def test_runtime_refreshes_when_session_bind_changes():
    runtime = PlatformLimitsRuntime()
    factory_one = await _make_session_factory()
    factory_two = await _make_session_factory()

    async with factory_one() as session:
        session.add(
            User(
                email="one@example.com",
                hashed_password="hashed",
                has_local_password=True,
                is_active=True,
                is_verified=True,
                role="rw",
            )
        )
        await session.commit()

    async with factory_two() as session:
        session.add_all(
            [
                User(
                    email="two@example.com",
                    hashed_password="hashed",
                    has_local_password=True,
                    is_active=True,
                    is_verified=True,
                    role="rw",
                ),
                User(
                    email="three@example.com",
                    hashed_password="hashed",
                    has_local_password=True,
                    is_active=True,
                    is_verified=True,
                    role="rw",
                ),
            ]
        )
        await session.commit()

    async with factory_one() as session:
        snapshot_one = await runtime.ensure_snapshot(session)
    async with factory_two() as session:
        snapshot_two = await runtime.ensure_snapshot(session)

    assert snapshot_one.usage.registered_users == 1
    assert snapshot_two.usage.registered_users == 2
