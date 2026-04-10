from __future__ import annotations

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.metering import TierTemplate
from treadstone.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID, PlatformLimits
from treadstone.models.user import OAuthAccount, User
from treadstone.models.waitlist import WaitlistApplication


async def _seed_tier_templates(session: AsyncSession) -> None:
    session.add(
        TierTemplate(
            tier_name="free",
            compute_units_monthly=10,
            storage_capacity_gib=0,
            max_concurrent_running=1,
            max_sandbox_duration_seconds=1800,
            allowed_templates=["aio-sandbox-tiny", "aio-sandbox-small"],
            grace_period_seconds=600,
        )
    )
    await session.commit()


@pytest.fixture
async def session_factory():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        await _seed_tier_templates(session)

    async def override_get_session():
        async with factory() as session:
            yield session

    async def override_get_user_db():
        async with factory() as session:
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

    async def override_get_user_manager():
        async with factory() as session:
            db = SQLAlchemyUserDatabase(session, User, OAuthAccount)
            yield UserManager(db)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_user_db] = override_get_user_db
    app.dependency_overrides[get_user_manager] = override_get_user_manager

    yield factory

    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


async def _set_platform_limits(session_factory, **limits) -> None:
    async with session_factory() as session:
        row = await session.get(PlatformLimits, PLATFORM_LIMITS_SINGLETON_ID)
        if row is None:
            row = PlatformLimits(id=PLATFORM_LIMITS_SINGLETON_ID)
        for field, value in limits.items():
            setattr(row, field, value)
        session.add(row)
        await session.commit()
        await app.state.platform_limits_runtime.refresh_from_session(session)


@pytest.fixture
async def anon_client(session_factory):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_post_waitlist_succeeds_even_if_post_commit_refresh_fails(anon_client, session_factory, monkeypatch):
    async def failing_refresh(self, instance, attribute_names=None, with_for_update=None):
        raise RuntimeError("refresh lost after commit")

    monkeypatch.setattr(AsyncSession, "refresh", failing_refresh)

    response = await anon_client.post(
        "/v1/waitlist",
        json={
            "email": "retry-risk@example.com",
            "name": "Retry Risk",
            "target_tier": "pro",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "retry-risk@example.com"
    assert data["status"] == "pending"

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(WaitlistApplication).where(WaitlistApplication.email == "retry-risk@example.com")
                )
            )
            .scalars()
            .all()
        )

    assert len(rows) == 1


async def test_post_waitlist_respects_global_cap(anon_client, session_factory):
    await _set_platform_limits(session_factory, max_waitlist_applications=0)

    response = await anon_client.post(
        "/v1/waitlist",
        json={
            "email": "waitlist-cap@example.com",
            "name": "Waitlist Cap",
            "target_tier": "pro",
        },
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "waitlist_cap_exceeded"

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(WaitlistApplication).where(WaitlistApplication.email == "waitlist-cap@example.com")
                )
            )
            .scalars()
            .all()
        )

    assert rows == []
