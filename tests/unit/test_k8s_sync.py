"""Unit tests for K8s Watch + Reconciliation — conditions-based status derivation."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import User, utc_now
from treadstone.services.k8s_client import FakeK8sClient
from treadstone.services.k8s_sync import derive_status_from_sandbox_cr, handle_watch_event, reconcile, watch_loop


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
        "template": "aio-sandbox-tiny",
        "runtime_type": "aio",
        "labels": {},
        "auto_stop_interval": 15,
        "auto_delete_interval": -1,
        "status": SandboxStatus.CREATING,
        "version": 1,
        "endpoints": {},
        "k8s_sandbox_claim_name": "test-sb",
        "k8s_sandbox_name": "test-sb",
        "k8s_namespace": "treadstone-local",
        "gmt_created": utc_now(),
    }
    defaults.update(overrides)
    sb = Sandbox(**{k: v for k, v in defaults.items()})
    async with factory() as session:
        session.add(sb)
        await session.commit()
    return sb


def _cond(status: str = "False", reason: str = "DependenciesNotReady", message: str = "") -> dict:
    return {"type": "Ready", "status": status, "reason": reason, "message": message}


class TestDeriveStatusFromSandboxCR:
    def test_no_conditions_means_creating(self):
        cr = {"spec": {"replicas": 1}, "status": {}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.CREATING

    def test_ready_true_replicas_1_means_ready(self):
        cr = {"spec": {"replicas": 1}, "status": {"conditions": [_cond("True", "DependenciesReady")]}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.READY

    def test_ready_true_replicas_0_means_stopped(self):
        cr = {"spec": {"replicas": 0}, "status": {"conditions": [_cond("True", "DependenciesReady")]}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.STOPPED

    def test_reconciler_error_means_error(self):
        cr = {"spec": {"replicas": 1}, "status": {"conditions": [_cond("False", "ReconcilerError", "bad")]}}
        status, msg = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.ERROR
        assert msg == "bad"

    def test_dependencies_not_ready_means_creating(self):
        cr = {"spec": {"replicas": 1}, "status": {"conditions": [_cond("False", "DependenciesNotReady")]}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.CREATING

    def test_sandbox_expired_means_stopped(self):
        cr = {"spec": {"replicas": 1}, "status": {"conditions": [_cond("False", "SandboxExpired")]}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.STOPPED

    def test_dependencies_not_ready_replicas_0_means_stopped(self):
        cr = {"spec": {"replicas": 0}, "status": {"conditions": [_cond("False", "DependenciesNotReady")]}}
        status, _ = derive_status_from_sandbox_cr(cr)
        assert status == SandboxStatus.STOPPED


class TestHandleWatchEvent:
    async def test_modified_creating_to_ready(self, session_factory):
        await _create_sandbox(session_factory)
        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "100"},
            "spec": {"replicas": 1},
            "status": {
                "conditions": [{"type": "Ready", "status": "True", "reason": "DependenciesReady", "message": "ok"}],
                "serviceFQDN": "test-sb.treadstone-local.svc.cluster.local",
            },
        }
        await handle_watch_event("MODIFIED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
            assert sb.version == 2
            assert sb.k8s_resource_version == "100"

    async def test_deleted_from_deleting_marks_deleted(self, session_factory):
        await _create_sandbox(
            session_factory,
            status=SandboxStatus.DELETING,
            gmt_deleted=utc_now(),
        )
        cr = {"metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "200"}}
        await handle_watch_event("DELETED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb is not None
            assert sb.status == SandboxStatus.DELETED
            assert sb.gmt_deleted is not None

    async def test_deleted_from_ready_marks_error(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.READY)
        cr = {"metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "300"}}
        await handle_watch_event("DELETED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.ERROR

    async def test_modified_error_to_ready(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.ERROR, version=3)
        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "400"},
            "spec": {"replicas": 1},
            "status": {
                "conditions": [{"type": "Ready", "status": "True", "reason": "DependenciesReady", "message": "ok"}],
            },
        }
        await handle_watch_event("MODIFIED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
            assert sb.version == 4
            assert sb.k8s_resource_version == "400"

    async def test_modified_error_to_creating(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.ERROR, version=2)
        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "410"},
            "spec": {"replicas": 1},
            "status": {
                "conditions": [_cond("False", "DependenciesNotReady", "waiting for deps")],
            },
        }
        await handle_watch_event("MODIFIED", cr, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.CREATING
            assert sb.version == 3

    async def test_unknown_cr_ignored(self, session_factory):
        cr = {
            "metadata": {"name": "unknown-cr", "namespace": "treadstone-local", "resourceVersion": "500"},
            "spec": {"replicas": 1},
            "status": {"conditions": [_cond("True", "DependenciesReady")]},
        }
        await handle_watch_event("ADDED", cr, session_factory)


class TestReconcile:
    async def test_reconcile_updates_drift(self, session_factory):
        await _create_sandbox(session_factory, k8s_resource_version="old")
        k8s = FakeK8sClient()
        await k8s.create_sandbox_claim("test-sb", "aio-sandbox-tiny", "treadstone-local")
        k8s.simulate_sandbox_ready("test-sb", "treadstone-local")

        rv = await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
        assert rv != ""

    async def test_reconcile_missing_cr_stopped_stays_stopped(self, session_factory):
        """Empty List must not promote STOPPED to ERROR (policy=warn_only)."""
        await _create_sandbox(session_factory, status=SandboxStatus.STOPPED, k8s_resource_version="1")
        k8s = FakeK8sClient()

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.STOPPED

    async def test_reconcile_missing_cr_ready_stays_ready(self, session_factory):
        """Empty List must not demote READY to ERROR (policy=warn_only)."""
        await _create_sandbox(session_factory, status=SandboxStatus.READY, k8s_resource_version="1")
        k8s = FakeK8sClient()

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY

    async def test_reconcile_missing_cr_error_stays_error(self, session_factory):
        """Empty List must not re-mark ERROR (policy=warn_only, idempotent)."""
        await _create_sandbox(session_factory, status=SandboxStatus.ERROR, k8s_resource_version="1")
        k8s = FakeK8sClient()

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.ERROR
            assert sb.version == 1

    async def test_reconcile_missing_cr_deleting_marks_deleted(self, session_factory):
        await _create_sandbox(
            session_factory,
            status=SandboxStatus.DELETING,
            gmt_deleted=utc_now(),
        )
        k8s = FakeK8sClient()

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb is not None
            assert sb.status == SandboxStatus.DELETED
            assert sb.gmt_deleted is not None

    async def test_reconcile_error_to_ready(self, session_factory):
        await _create_sandbox(session_factory, status=SandboxStatus.ERROR, k8s_resource_version="old")
        k8s = FakeK8sClient()
        await k8s.create_sandbox_claim("test-sb", "aio-sandbox-tiny", "treadstone-local")
        k8s.simulate_sandbox_ready("test-sb", "treadstone-local")

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY

    async def test_reconcile_finds_cr_when_k8s_sandbox_name_mismatches_list_key(self, session_factory):
        """If k8s_sandbox_name is wrong but claim name matches the CR, reconcile must not mark missing."""
        await _create_sandbox(
            session_factory,
            k8s_sandbox_name="stale-wrong-name",
            k8s_sandbox_claim_name="test-sb",
            status=SandboxStatus.ERROR,
            k8s_resource_version="old",
        )
        k8s = FakeK8sClient()
        await k8s.create_sandbox_claim("test-sb", "aio-sandbox-tiny", "treadstone-local")
        k8s.simulate_sandbox_ready("test-sb", "treadstone-local")

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY

    async def test_reconcile_returns_resource_version(self, session_factory):
        k8s = FakeK8sClient()
        await k8s.create_sandbox_claim("some-sb", "aio-sandbox-tiny", "treadstone-local")
        k8s.simulate_sandbox_ready("some-sb", "treadstone-local")

        rv = await reconcile("treadstone-local", k8s, session_factory)
        assert rv.isdigit()

    async def test_reconcile_stale_cr_does_not_overwrite_db(self, session_factory):
        """LIST can return an old CR; do not downgrade READY to ERROR from stale ReconcilerError."""
        await _create_sandbox(
            session_factory,
            status=SandboxStatus.READY,
            version=2,
            k8s_resource_version="1000",
        )
        k8s = FakeK8sClient()
        await k8s.create_sandbox_claim("test-sb", "aio-sandbox-tiny", "treadstone-local")
        k8s.simulate_sandbox_ready("test-sb", "treadstone-local")
        stale = k8s._sandboxes["treadstone-local/test-sb"]
        stale["metadata"]["resourceVersion"] = "10"
        stale["status"]["conditions"] = [
            {"type": "Ready", "status": "False", "reason": "ReconcilerError", "message": "stale failure"},
        ]

        await reconcile("treadstone-local", k8s, session_factory)

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
            assert sb.k8s_resource_version == "1000"


class TestWatchLoop:
    async def test_watch_event_updates_db(self, session_factory):
        """Watch MODIFIED event should transition sandbox from CREATING to READY."""
        await _create_sandbox(session_factory)
        k8s = FakeK8sClient()

        cr = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "50"},
            "spec": {"replicas": 1},
            "status": {
                "conditions": [_cond("True", "DependenciesReady", "ok")],
                "serviceFQDN": "test-sb.treadstone-local.svc.cluster.local",
            },
        }
        k8s.enqueue_watch_event("MODIFIED", cr)
        k8s.stop_watch()

        await watch_loop("treadstone-local", k8s, session_factory, resource_version="1")

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.READY
            assert sb.k8s_resource_version == "50"

    async def test_watch_multiple_events(self, session_factory):
        """Multiple Watch events should be processed in order."""
        await _create_sandbox(session_factory)
        k8s = FakeK8sClient()

        cr_ready = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "10"},
            "spec": {"replicas": 1},
            "status": {"conditions": [_cond("True", "DependenciesReady", "ok")]},
        }
        cr_stopped = {
            "metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "11"},
            "spec": {"replicas": 0},
            "status": {"conditions": [_cond("True", "DependenciesReady", "scaled down")]},
        }
        k8s.enqueue_watch_event("MODIFIED", cr_ready)
        k8s.enqueue_watch_event("MODIFIED", cr_stopped)
        k8s.stop_watch()

        await watch_loop("treadstone-local", k8s, session_factory, resource_version="1")

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb.status == SandboxStatus.STOPPED
            assert sb.k8s_resource_version == "11"

    async def test_watch_deleted_event(self, session_factory):
        """Watch DELETED event for a DELETING sandbox should soft-delete the row."""
        await _create_sandbox(session_factory, status=SandboxStatus.DELETING)
        k8s = FakeK8sClient()

        cr = {"metadata": {"name": "test-sb", "namespace": "treadstone-local", "resourceVersion": "99"}}
        k8s.enqueue_watch_event("DELETED", cr)
        k8s.stop_watch()

        await watch_loop("treadstone-local", k8s, session_factory, resource_version="1")

        async with session_factory() as session:
            sb = await session.get(Sandbox, "sb00000000test1234")
            assert sb is not None
            assert sb.status == SandboxStatus.DELETED
            assert sb.gmt_deleted is not None

    async def test_watch_loop_completes_on_stream_end(self, session_factory):
        """Watch loop should return gracefully when the stream ends."""
        k8s = FakeK8sClient()
        k8s.stop_watch()

        await asyncio.wait_for(
            watch_loop("treadstone-local", k8s, session_factory, resource_version="0"),
            timeout=2.0,
        )
