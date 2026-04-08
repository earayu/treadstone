from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.api.sandboxes import _get_owned_sandbox_with_active_web_link, _upsert_web_link
from treadstone.core.database import Base
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import Role, User, utc_now


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _make_user(user_id: str = "user123") -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        has_local_password=True,
        role=Role.RW.value,
    )


def _make_sandbox(owner_id: str, sandbox_id: str = "sb123") -> Sandbox:
    now = utc_now()
    return Sandbox(
        id=sandbox_id,
        name="demo",
        owner_id=owner_id,
        template="aio-sandbox-tiny",
        labels={},
        auto_stop_interval=15,
        auto_delete_interval=-1,
        provision_mode="claim",
        persist=False,
        k8s_namespace="default",
        status=SandboxStatus.READY,
        endpoints={},
        version=1,
        gmt_created=now,
        gmt_last_active=now,
    )


class TestSandboxWebLinkQueryShape:
    async def test_get_owned_sandbox_with_active_web_link_uses_one_query(self, session, monkeypatch):
        user = _make_user()
        sandbox = _make_sandbox(user.id)
        link = SandboxWebLink(
            id="swl123",
            sandbox_id=sandbox.id,
            created_by_user_id=user.id,
            gmt_created=utc_now(),
            gmt_updated=utc_now(),
        )
        session.add_all([user, sandbox, link])
        await session.commit()

        execute_count = 0
        original_execute = session.execute

        async def counted_execute(*args, **kwargs):
            nonlocal execute_count
            execute_count += 1
            return await original_execute(*args, **kwargs)

        monkeypatch.setattr(session, "execute", counted_execute)

        loaded_sandbox, loaded_link = await _get_owned_sandbox_with_active_web_link(session, sandbox.id, user.id)

        assert loaded_sandbox is not None
        assert loaded_sandbox.id == sandbox.id
        assert loaded_link is not None
        assert loaded_link.id == link.id
        assert execute_count == 1

    async def test_upsert_web_link_reuses_existing_row_without_reselect(self, session, monkeypatch):
        user = _make_user()
        sandbox = _make_sandbox(user.id)
        existing = SandboxWebLink(
            id="swlold",
            sandbox_id=sandbox.id,
            created_by_user_id=user.id,
            gmt_created=utc_now(),
            gmt_updated=datetime.now(UTC) - timedelta(hours=1),
            gmt_expires=datetime.now(UTC) - timedelta(minutes=5),
            gmt_deleted=utc_now(),
        )
        session.add_all([user, sandbox, existing])
        await session.commit()

        execute_count = 0
        original_execute = session.execute

        async def counted_execute(*args, **kwargs):
            nonlocal execute_count
            execute_count += 1
            return await original_execute(*args, **kwargs)

        monkeypatch.setattr(session, "execute", counted_execute)

        link = await _upsert_web_link(session, sandbox, user.id, existing_link=existing)

        assert link is existing
        assert link.id != "swlold"
        assert link.created_by_user_id == user.id
        assert link.gmt_deleted is None
        assert link.gmt_expires is None
        assert execute_count == 0
