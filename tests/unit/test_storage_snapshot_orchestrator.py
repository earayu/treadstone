"""Integrated unit tests for cold snapshot orchestration."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base
from treadstone.models.metering import StorageLedger, StorageState
from treadstone.models.sandbox import Sandbox, SandboxPendingOperation, SandboxStatus, StorageBackendMode
from treadstone.models.user import User, utc_now
from treadstone.services.k8s_client import (
    LABEL_OWNER_ID,
    LABEL_PROVISION_MODE,
    LABEL_SANDBOX_ID,
    LABEL_STORAGE_ROLE,
    LABEL_TEMPLATE,
    LABEL_WORKLOAD,
    PROVISION_MODE_DIRECT,
    STORAGE_ROLE_WORKSPACE,
    WORKLOAD_SANDBOX,
    FakeK8sClient,
)
from treadstone.services.metering_service import MeteringService
from treadstone.services.sandbox_service import SandboxService
from treadstone.services.storage_snapshot_orchestrator import run_storage_snapshot_tick


async def _create_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id="user0001234567890", email="snapshot@test.com", hashed_password="x", role="admin"))
        await session.commit()
    return engine, factory


async def _create_live_sandbox(
    factory: async_sessionmaker[AsyncSession],
    k8s: FakeK8sClient,
    *,
    sandbox_id: str,
    status: str = SandboxStatus.STOPPED,
) -> None:
    labels = {
        LABEL_SANDBOX_ID: sandbox_id,
        LABEL_OWNER_ID: "user0001234567890",
        LABEL_TEMPLATE: "aio-sandbox-tiny",
        LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        LABEL_WORKLOAD: WORKLOAD_SANDBOX,
        LABEL_STORAGE_ROLE: STORAGE_ROLE_WORKSPACE,
    }
    await k8s.create_sandbox(
        name=sandbox_id,
        namespace="treadstone-local",
        image="ghcr.io/agent-infra/sandbox:1.0.0.152",
        container_port=8080,
        resources={"requests": {"cpu": "250m", "memory": "1Gi"}, "limits": {"cpu": "250m", "memory": "1Gi"}},
        replicas=0 if status == SandboxStatus.STOPPED else 1,
        volume_claim_templates=[
            {
                "metadata": {"name": STORAGE_ROLE_WORKSPACE, "labels": labels},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": "treadstone-workspace",
                    "resources": {"requests": {"storage": "5Gi"}},
                },
            }
        ],
        labels={
            LABEL_SANDBOX_ID: sandbox_id,
            LABEL_OWNER_ID: "user0001234567890",
            LABEL_TEMPLATE: "aio-sandbox-tiny",
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        },
        pod_labels={
            LABEL_SANDBOX_ID: sandbox_id,
            LABEL_OWNER_ID: "user0001234567890",
            LABEL_WORKLOAD: WORKLOAD_SANDBOX,
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        },
    )
    if status == SandboxStatus.READY:
        k8s.simulate_sandbox_ready(sandbox_id, "treadstone-local")

    async with factory() as session:
        session.add(
            Sandbox(
                id=sandbox_id,
                name=sandbox_id,
                owner_id="user0001234567890",
                template="aio-sandbox-tiny",
                runtime_type="aio",
                labels={},
                auto_stop_interval=15,
                auto_delete_interval=-1,
                provision_mode=PROVISION_MODE_DIRECT,
                persist=True,
                storage_size="5Gi",
                k8s_sandbox_name=sandbox_id,
                k8s_namespace="treadstone-local",
                status=status,
                storage_backend_mode=StorageBackendMode.LIVE_DISK,
                endpoints={},
                version=1,
                gmt_created=utc_now(),
                gmt_stopped=utc_now() if status == SandboxStatus.STOPPED else None,
                gmt_started=utc_now() if status == SandboxStatus.READY else None,
            )
        )
        await session.commit()


async def test_snapshot_tick_moves_persistent_sandbox_to_cold_storage():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbcoldsnapshot000001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.COLD
        assert sandbox.pending_operation is None
        assert sandbox.storage_backend_mode == StorageBackendMode.STANDARD_SNAPSHOT
        assert sandbox.snapshot_k8s_volume_snapshot_name is not None
        assert sandbox.k8s_workspace_pvc_name is None
        assert sandbox.k8s_workspace_pv_name is None

    assert await k8s.get_sandbox(sandbox_id, "treadstone-local") is None
    assert await k8s.list_persistent_volume_claims("treadstone-local", labels={LABEL_SANDBOX_ID: sandbox_id}) == []
    assert await k8s.get_volume_snapshot(f"{sandbox_id}-workspace-snapshot", "treadstone-local") is not None

    await engine.dispose()


async def test_snapshot_tick_waits_for_stop_before_creating_snapshot():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbwaitforstop000001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.READY)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.READY
        assert sandbox.pending_operation == SandboxPendingOperation.SNAPSHOTTING
        assert sandbox.snapshot_k8s_volume_snapshot_name is None

    assert await k8s.get_volume_snapshot(f"{sandbox_id}-workspace-snapshot", "treadstone-local") is None

    await k8s.scale_sandbox(sandbox_id, "treadstone-local", 0)
    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.COLD
        assert sandbox.pending_operation is None

    await engine.dispose()


async def test_restore_tick_moves_cold_sandbox_back_to_stopped_live_disk():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbcoldrestore0000001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    async with factory() as session:
        metering = MeteringService()
        await metering.record_storage_allocation(session, "user0001234567890", sandbox_id, 5)
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.RESTORING
        sandbox.pending_operation_target_status = SandboxStatus.STOPPED
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.STOPPED
        assert sandbox.pending_operation is None
        assert sandbox.storage_backend_mode == StorageBackendMode.LIVE_DISK
        assert sandbox.snapshot_k8s_volume_snapshot_name is None
        assert sandbox.k8s_workspace_pvc_name is not None
        assert sandbox.k8s_workspace_pv_name is not None

        ledger = (
            await session.execute(
                select(StorageLedger).where(
                    StorageLedger.sandbox_id == sandbox_id,
                    StorageLedger.storage_state == StorageState.ACTIVE,
                )
            )
        ).scalar_one()
        assert ledger.backend_mode == StorageBackendMode.LIVE_DISK

    restored = await k8s.get_sandbox(sandbox_id, "treadstone-local")
    assert restored is not None
    assert restored["spec"]["replicas"] == 0
    assert await k8s.get_volume_snapshot(f"{sandbox_id}-workspace-snapshot", "treadstone-local") is None

    await engine.dispose()


async def test_restore_tick_falls_back_to_stopped_live_disk_when_runtime_errors():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbrestoreerror00001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    async with factory() as session:
        metering = MeteringService()
        await metering.record_storage_allocation(session, "user0001234567890", sandbox_id, 5)
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.RESTORING
        sandbox.pending_operation_target_status = SandboxStatus.READY
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    restored = await k8s.get_sandbox(sandbox_id, "treadstone-local")
    assert restored is not None
    restored["metadata"]["resourceVersion"] = "9"
    restored["status"]["conditions"] = [
        {"type": "Ready", "status": "False", "reason": "ReconcilerError", "message": "restore failed"}
    ]
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.STOPPED
        assert sandbox.pending_operation is None
        assert sandbox.storage_backend_mode == StorageBackendMode.LIVE_DISK
        assert sandbox.snapshot_k8s_volume_snapshot_name is None
        assert sandbox.status_message == "restore failed"

    await engine.dispose()


async def test_start_on_cold_restores_and_returns_to_ready():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbcoldstartready001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        service = SandboxService(session=session, k8s_client=k8s, metering=MeteringService())
        sandbox = await service.start(sandbox_id, "user0001234567890")
        assert sandbox.pending_operation == SandboxPendingOperation.RESTORING
        assert sandbox.pending_operation_target_status == SandboxStatus.READY

    await run_storage_snapshot_tick(factory, k8s)
    k8s.simulate_sandbox_ready(sandbox_id, "treadstone-local")
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.READY
        assert sandbox.pending_operation is None
        assert sandbox.storage_backend_mode == StorageBackendMode.LIVE_DISK

    await engine.dispose()


async def test_snapshot_tick_fails_instead_of_reusing_stale_bound_snapshot():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbstalesnapshot0001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    snapshot_name = f"{sandbox_id}-workspace-snapshot"
    await k8s.create_volume_snapshot(
        name=snapshot_name,
        namespace="treadstone-local",
        source_pvc_name=f"{sandbox_id}-{STORAGE_ROLE_WORKSPACE}",
        snapshot_class_name="treadstone-workspace-snapshot",
    )

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        sandbox.storage_backend_mode = StorageBackendMode.LIVE_DISK
        sandbox.snapshot_k8s_volume_snapshot_name = snapshot_name
        sandbox.snapshot_k8s_volume_snapshot_content_name = f"vsc-{snapshot_name}"
        sandbox.gmt_snapshotted = utc_now()
        sandbox.gmt_restored = utc_now()
        session.add(sandbox)
        await session.commit()

    async def _fail_delete_snapshot(name: str, namespace: str) -> bool:
        raise RuntimeError("cleanup failed")

    k8s.delete_volume_snapshot = _fail_delete_snapshot  # type: ignore[assignment]
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        assert sandbox.status == SandboxStatus.STOPPED
        assert sandbox.pending_operation is None
        assert sandbox.storage_backend_mode == StorageBackendMode.LIVE_DISK
        assert "Failed to clean up previous snapshot" in sandbox.status_message
        assert sandbox.snapshot_k8s_volume_snapshot_name == snapshot_name

    await engine.dispose()


async def test_delete_cold_sandbox_deletes_snapshot_and_releases_storage_ledger():
    engine, factory = await _create_factory()
    k8s = FakeK8sClient()
    sandbox_id = "sbcolddelete0000001"
    await _create_live_sandbox(factory, k8s, sandbox_id=sandbox_id, status=SandboxStatus.STOPPED)

    async with factory() as session:
        metering = MeteringService()
        await metering.record_storage_allocation(session, "user0001234567890", sandbox_id, 5)
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.pending_operation = SandboxPendingOperation.SNAPSHOTTING
        session.add(sandbox)
        await session.commit()

    await run_storage_snapshot_tick(factory, k8s)
    await run_storage_snapshot_tick(factory, k8s)

    async with factory() as session:
        service = SandboxService(session=session, k8s_client=k8s, metering=MeteringService())
        sandbox = await service.delete(sandbox_id, "user0001234567890")
        assert sandbox.status == SandboxStatus.DELETED
        assert sandbox.gmt_deleted is not None

    async with factory() as session:
        ledger = (
            await session.execute(select(StorageLedger).where(StorageLedger.sandbox_id == sandbox_id))
        ).scalar_one()
        assert ledger.storage_state == StorageState.DELETED

    assert await k8s.get_volume_snapshot(f"{sandbox_id}-workspace-snapshot", "treadstone-local") is None
    await engine.dispose()
