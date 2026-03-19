"""Unit tests for K8s Watch + Reconciliation."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import User, utc_now
from treadstone.services.k8s_client import FakeK8sClient
from treadstone.services.k8s_sync import handle_watch_event, reconcile


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        user = User(id="user0001234567890", email="test@test.com", hashed_password="x", role="admin")
        session.add(user)
        await session.commit()

    yield factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _create_sandbox(factory, **overrides) -> Sandbox:
    defaults = {
        "id": "sb00000000test1234",
        "name": "test-sb",
        "owner_id": "user0001234567890",
        "template": "python-dev",
        "runtime_type": "aio",
        "image": "img:latest",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.CREATING,
        "version": 1,
        "endpoints": {},
        "k8s_sandbox_name": "test-sb",
        "k8s_namespace": "treadstone",
        "gmt_created": utc_now(),
    }
    defaults.update(overrides)
    sb = Sandbox(**{k: v for k, v in defaults.items()})
    async with factory() as session:
        session.add(sb)
        await session.commit()
    return sb


class TestHandleWatchEvent:
    async def test_modified_creating_to_ready(self, session_factory):
        await _create_sandbox(session_factory)
        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone", "resourceVersion": "100"},
            "status": {"phase": "Ready"},
        }
        await handle_watch_event("MODIFIED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
            assert sb.version == 2
            assert sb.k8s_resource_version == "100"

    async def test_deleted_from_deleting_marks_deleted(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.DELETING)
        cr = {"metadata": {"name": "test-sb", "namespace": "treadstone", "resourceVersion": "200"}}
        await handle_watch_event("DELETED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.DELETED

    async def test_deleted_from_ready_marks_error(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.READY)
        cr = {"metadata": {"name": "test-sb", "namespace": "treadstone", "resourceVersion": "300"}}
        await handle_watch_event("DELETED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.ERROR

    async def test_invalid_transition_skipped(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.DELETED, version=5)
        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone", "resourceVersion": "400"},
            "status": {"phase": "Ready"},
        }
        await handle_watch_event("MODIFIED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.DELETED
            assert sb.version == 5

    async def test_unknown_cr_ignored(self, session_factory):
        cr = {
            "metadata": {"name": "unknown-cr", "namespace": "treadstone", "resourceVersion": "500"},
            "status": {"phase": "Ready"},
        }
        await handle_watch_event("ADDED", cr, session_factory)


class TestReconcile:
    async def test_reconcile_updates_drift(self, session_factory):
        await _create_sandbox(session_factory, k8s_resource_version="old")
        k8s = FakeK8sClient()
        await k8s.create_sandbox_cr("test-sb", "python-dev", "treadstone", "img:latest")
        await k8s.start_sandbox_cr("test-sb", "treadstone")

        await reconcile("treadstone", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY

    async def test_reconcile_missing_cr_marks_error(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.READY)
        k8s = FakeK8sClient()

        await reconcile("treadstone", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.ERROR

    async def test_reconcile_missing_cr_deleting_marks_deleted(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.DELETING)
        k8s = FakeK8sClient()

        await reconcile("treadstone", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.DELETED
