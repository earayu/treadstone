"""Cold snapshot orchestration for persistent direct sandboxes.

This module owns the provider-specific K8s snapshot workflow used by the
SandboxService request path:
  snapshot: stop -> VolumeSnapshot -> release Sandbox CR/PVC/PV -> cold
  restore:  cold -> recreate Sandbox CR from VolumeSnapshot -> live disk

The public product model stays sandbox-centric. Snapshot objects remain an
internal implementation detail bound 1:1 to the sandbox row.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from treadstone.config import settings
from treadstone.core.errors import StorageSnapshotBackendNotReadyError, TemplateNotFoundError
from treadstone.identity.models.user import utc_now
from treadstone.infra.services.k8s_client import (
    ANNOTATION_CREATED_AT,
    ANNOTATION_SANDBOX_NAME,
    LABEL_OWNER_ID,
    LABEL_PROVISION_MODE,
    LABEL_SANDBOX_ID,
    LABEL_STORAGE_ROLE,
    LABEL_TEMPLATE,
    LABEL_WORKLOAD,
    PROVISION_MODE_DIRECT,
    SNAPSHOT_API_GROUP,
    STORAGE_ROLE_WORKSPACE,
    WORKLOAD_SANDBOX,
    K8sClientProtocol,
    get_k8s_client,
)
from treadstone.metering.services.metering_service import MeteringService
from treadstone.sandbox.models.sandbox import Sandbox, SandboxPendingOperation, SandboxStatus, StorageBackendMode

__all__ = [
    "SNAPSHOT_TICK_INTERVAL",
    "StorageSnapshotOrchestrator",
    "StorageSnapshotBackendProtocol",
    "AckStorageSnapshotBackend",
    "run_storage_snapshot_tick",
]

logger = logging.getLogger(__name__)

SNAPSHOT_TICK_INTERVAL = 15

_metering = MeteringService()


class StorageSnapshotBackendProtocol(Protocol):
    async def ensure_ready(self) -> None: ...

    async def create_snapshot(self, sandbox: Sandbox, pvc_name: str) -> str: ...

    async def get_snapshot(self, sandbox: Sandbox) -> dict | None: ...

    async def get_snapshot_content(self, sandbox: Sandbox) -> dict | None: ...

    async def delete_bound_snapshot(self, sandbox: Sandbox) -> bool: ...


class AckStorageSnapshotBackend:
    """ACK-first snapshot backend backed by VolumeSnapshot resources."""

    def __init__(self, k8s: K8sClientProtocol) -> None:
        self.k8s = k8s

    async def ensure_ready(self) -> None:
        snapshot_class = await self.k8s.get_volume_snapshot_class(settings.sandbox_volume_snapshot_class)
        if snapshot_class is None:
            raise StorageSnapshotBackendNotReadyError(settings.sandbox_volume_snapshot_class)

    async def create_snapshot(self, sandbox: Sandbox, pvc_name: str) -> str:
        snapshot_name = sandbox.snapshot_k8s_volume_snapshot_name or _snapshot_name(sandbox.id)
        await self.k8s.create_volume_snapshot(
            name=snapshot_name,
            namespace=sandbox.k8s_namespace,
            source_pvc_name=pvc_name,
            snapshot_class_name=settings.sandbox_volume_snapshot_class,
            labels=_workspace_labels(sandbox),
            annotations={ANNOTATION_SANDBOX_NAME: sandbox.name},
        )
        return snapshot_name

    async def get_snapshot(self, sandbox: Sandbox) -> dict | None:
        snapshot_name = sandbox.snapshot_k8s_volume_snapshot_name
        if not snapshot_name:
            return None
        return await self.k8s.get_volume_snapshot(snapshot_name, sandbox.k8s_namespace)

    async def get_snapshot_content(self, sandbox: Sandbox) -> dict | None:
        content_name = sandbox.snapshot_k8s_volume_snapshot_content_name
        if not content_name:
            snapshot = await self.get_snapshot(sandbox)
            if snapshot is None:
                return None
            content_name = snapshot.get("status", {}).get("boundVolumeSnapshotContentName")
        if not content_name:
            return None
        return await self.k8s.get_volume_snapshot_content(content_name)

    async def delete_bound_snapshot(self, sandbox: Sandbox) -> bool:
        deleted_any = False
        content_name = sandbox.snapshot_k8s_volume_snapshot_content_name
        snapshot_name = sandbox.snapshot_k8s_volume_snapshot_name

        if content_name:
            await self.k8s.set_volume_snapshot_content_deletion_policy(content_name, "Delete")

        if snapshot_name:
            snapshot = await self.k8s.get_volume_snapshot(snapshot_name, sandbox.k8s_namespace)
            if snapshot is not None:
                content_name = content_name or snapshot.get("status", {}).get("boundVolumeSnapshotContentName")
                await self.k8s.delete_volume_snapshot(snapshot_name, sandbox.k8s_namespace)
                deleted_any = True

        if content_name:
            content = await self.k8s.get_volume_snapshot_content(content_name)
            if content is not None:
                await self.k8s.delete_volume_snapshot_content(content_name)
                deleted_any = True

        return deleted_any


class StorageSnapshotOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        k8s_client: K8sClientProtocol | None = None,
        metering: MeteringService | None = None,
        backend: StorageSnapshotBackendProtocol | None = None,
    ) -> None:
        self.session = session
        self.k8s = k8s_client or get_k8s_client()
        self._metering = metering or _metering
        self.backend = backend or AckStorageSnapshotBackend(self.k8s)

    async def process_sandbox(self, sandbox: Sandbox) -> None:
        if sandbox.pending_operation == SandboxPendingOperation.SNAPSHOTTING:
            await self._process_snapshotting(sandbox)
            return
        if sandbox.pending_operation == SandboxPendingOperation.RESTORING:
            await self._process_restoring(sandbox)

    async def _process_snapshotting(self, sandbox: Sandbox) -> None:
        if sandbox.persist and sandbox.storage_backend_mode is None:
            logger.warning(
                "Sandbox %s has persist=True but storage_backend_mode is NULL; defaulting to live_disk",
                sandbox.id,
            )
            sandbox.storage_backend_mode = StorageBackendMode.LIVE_DISK
            self.session.add(sandbox)

        try:
            await self.backend.ensure_ready()
        except Exception as exc:
            await self._fail_snapshot(sandbox, str(exc))
            return

        if (
            sandbox.storage_backend_mode == StorageBackendMode.LIVE_DISK
            and sandbox.snapshot_k8s_volume_snapshot_name
            and sandbox.gmt_restored is not None
            and sandbox.gmt_snapshotted is not None
            and sandbox.gmt_restored >= sandbox.gmt_snapshotted
        ):
            try:
                await self.backend.delete_bound_snapshot(sandbox)
                self._clear_snapshot_binding(sandbox)
            except Exception as exc:
                logger.exception("Failed to clean up stale snapshot binding for sandbox %s", sandbox.id)
                await self._fail_snapshot(
                    sandbox,
                    f"Failed to clean up previous snapshot before creating a new one: {exc}",
                )
                return
            # Advance gmt_snapshotted so the stale condition
            # (gmt_restored >= gmt_snapshotted) no longer holds on the next
            # tick.  Without this the snapshot created by the next tick would
            # be mistaken for a stale leftover and deleted, ad infinitum.
            sandbox.gmt_snapshotted = utc_now()
            self.session.add(sandbox)
            return

        if sandbox.storage_backend_mode == StorageBackendMode.STANDARD_SNAPSHOT:
            sandbox.pending_operation = None
            sandbox.status = SandboxStatus.COLD
            sandbox.status_message = None
            self.session.add(sandbox)
            return

        if sandbox.snapshot_k8s_volume_snapshot_name is None:
            from treadstone.infra.services.k8s_sync import derive_status_from_sandbox_cr

            cr_name = sandbox.k8s_sandbox_name or sandbox.id
            cr = await self.k8s.get_sandbox(cr_name, sandbox.k8s_namespace)
            if cr is None:
                await self._fail_snapshot(sandbox, "Sandbox CR disappeared before the sandbox stopped for snapshot.")
                return

            derived_status, message = derive_status_from_sandbox_cr(cr)
            if derived_status == SandboxStatus.ERROR:
                await self._fail_snapshot(
                    sandbox,
                    message or "Sandbox entered an error state while waiting to stop for snapshot.",
                )
                return
            if derived_status != SandboxStatus.STOPPED:
                sandbox.status_message = message or "Waiting for sandbox to stop before snapshot."
                self.session.add(sandbox)
                return

            if not await self._refresh_workspace_binding(sandbox):
                await self._fail_snapshot(sandbox, "Failed to locate workspace PVC for snapshot.")
                return
            if sandbox.k8s_workspace_pvc_name is None:
                await self._fail_snapshot(sandbox, "Workspace PVC is not available for snapshot.")
                return
            try:
                logger.info(
                    "Creating cold snapshot for sandbox %s from PVC %s in namespace %s",
                    sandbox.id,
                    sandbox.k8s_workspace_pvc_name,
                    sandbox.k8s_namespace,
                )
                sandbox.snapshot_k8s_volume_snapshot_name = await self.backend.create_snapshot(
                    sandbox,
                    sandbox.k8s_workspace_pvc_name,
                )
                sandbox.status_message = "Creating cold snapshot."
                self.session.add(sandbox)
            except Exception as exc:
                await self._fail_snapshot(sandbox, f"Failed to create cold snapshot: {exc}")
            return

        snapshot = await self.backend.get_snapshot(sandbox)
        if snapshot is None:
            await self._fail_snapshot(sandbox, "Snapshot asset disappeared before it became ready.")
            return

        content_name = snapshot.get("status", {}).get("boundVolumeSnapshotContentName")
        if content_name and sandbox.snapshot_k8s_volume_snapshot_content_name != content_name:
            sandbox.snapshot_k8s_volume_snapshot_content_name = content_name

        if not snapshot.get("status", {}).get("readyToUse"):
            sandbox.status_message = "Waiting for snapshot to become ready."
            self.session.add(sandbox)
            return

        content = await self.backend.get_snapshot_content(sandbox)
        if content is not None:
            sandbox.snapshot_k8s_volume_snapshot_content_name = content.get("metadata", {}).get("name")
            sandbox.snapshot_provider_id = content.get("status", {}).get("snapshotHandle")
        logger.info(
            "Cold snapshot became ready for sandbox %s (snapshot=%s content=%s provider_id=%s)",
            sandbox.id,
            sandbox.snapshot_k8s_volume_snapshot_name,
            sandbox.snapshot_k8s_volume_snapshot_content_name,
            sandbox.snapshot_provider_id,
        )
        sandbox.gmt_snapshotted = utc_now()

        try:
            await self._release_live_workspace_assets(sandbox)
        except Exception as exc:
            logger.exception("Snapshot cleanup failed for sandbox %s", sandbox.id)
            await self.backend.delete_bound_snapshot(sandbox)
            self._clear_snapshot_binding(sandbox)
            await self._fail_snapshot(sandbox, f"Failed to release live disk after snapshot: {exc}")
            return

        cr_name = sandbox.k8s_sandbox_name or sandbox.id
        cr = await self.k8s.get_sandbox(cr_name, sandbox.k8s_namespace)
        pvc = (
            await self.k8s.get_persistent_volume_claim(sandbox.k8s_workspace_pvc_name, sandbox.k8s_namespace)
            if sandbox.k8s_workspace_pvc_name
            else None
        )
        pv = (
            await self.k8s.get_persistent_volume(sandbox.k8s_workspace_pv_name)
            if sandbox.k8s_workspace_pv_name
            else None
        )
        if cr is not None or pvc is not None or pv is not None:
            sandbox.status_message = "Waiting for live disk cleanup."
            self.session.add(sandbox)
            return

        sandbox.status = SandboxStatus.COLD
        sandbox.pending_operation = None
        sandbox.storage_backend_mode = StorageBackendMode.STANDARD_SNAPSHOT
        sandbox.status_message = None
        sandbox.workspace_zone = None
        sandbox.workspace_volume_handle = None
        sandbox.k8s_workspace_pv_name = None
        sandbox.k8s_workspace_pvc_name = None
        logger.info(
            "Cold snapshot cutover completed for sandbox %s (snapshot=%s provider_id=%s)",
            sandbox.id,
            sandbox.snapshot_k8s_volume_snapshot_name,
            sandbox.snapshot_provider_id,
        )
        await self._metering.update_storage_backend_mode(
            self.session,
            sandbox.id,
            StorageBackendMode.STANDARD_SNAPSHOT,
        )
        self.session.add(sandbox)

    async def _process_restoring(self, sandbox: Sandbox) -> None:
        try:
            await self.backend.ensure_ready()
        except Exception as exc:
            await self._fail_restore(sandbox, str(exc))
            return

        if not sandbox.snapshot_k8s_volume_snapshot_name:
            await self._fail_restore(sandbox, "Cold sandbox has no bound snapshot to restore from.")
            return

        cr_name = sandbox.k8s_sandbox_name or sandbox.id
        cr = await self.k8s.get_sandbox(cr_name, sandbox.k8s_namespace)

        if cr is None:
            try:
                await self._create_restored_sandbox(sandbox, replicas=1)
                sandbox.status_message = "Restoring sandbox from cold storage."
                self.session.add(sandbox)
            except Exception as exc:
                await self._fail_restore(sandbox, f"Failed to create restored sandbox: {exc}")
            return

        await self._refresh_workspace_binding(sandbox)
        from treadstone.infra.services.k8s_sync import derive_status_from_sandbox_cr

        derived_status, message = derive_status_from_sandbox_cr(cr)
        if derived_status == SandboxStatus.ERROR:
            await self._complete_restore_to_live_disk(
                sandbox,
                final_status=SandboxStatus.STOPPED,
                status_message=message or "Restore materialized the workspace, but the sandbox failed to become ready.",
            )
            return

        if sandbox.k8s_workspace_pvc_name is None or sandbox.k8s_workspace_pv_name is None:
            sandbox.status_message = "Waiting for restored workspace disk."
            self.session.add(sandbox)
            return

        if derived_status != SandboxStatus.READY:
            sandbox.status_message = message or "Waiting for restored sandbox to become ready."
            self.session.add(sandbox)
            return

        await self._complete_restore_to_live_disk(sandbox, final_status=SandboxStatus.READY)

    async def _complete_restore_to_live_disk(
        self,
        sandbox: Sandbox,
        *,
        final_status: str,
        status_message: str | None = None,
    ) -> None:
        sandbox.status = final_status
        sandbox.pending_operation = None
        sandbox.storage_backend_mode = StorageBackendMode.LIVE_DISK
        sandbox.status_message = status_message
        sandbox.gmt_restored = utc_now()
        if final_status == SandboxStatus.READY:
            sandbox.gmt_started = sandbox.gmt_started or utc_now()
        await self._metering.update_storage_backend_mode(
            self.session,
            sandbox.id,
            StorageBackendMode.LIVE_DISK,
        )
        if final_status == SandboxStatus.READY:
            try:
                await self._metering.open_compute_session(self.session, sandbox.id, sandbox.owner_id, sandbox.template)
            except Exception:
                logger.exception(
                    "Failed to open compute session for restored sandbox %s; reconcile will repair", sandbox.id
                )
        self.session.add(sandbox)

        try:
            deleted_snapshot = await self.backend.delete_bound_snapshot(sandbox)
        except Exception:
            logger.exception("Failed to clean up snapshot after restoring sandbox %s", sandbox.id)
            cleanup_prefix = status_message or (
                "Restored sandbox." if final_status == SandboxStatus.READY else "Restored sandbox workspace."
            )
            sandbox.status_message = f"{cleanup_prefix} Snapshot cleanup is pending."
            self.session.add(sandbox)
            return

        if deleted_snapshot or sandbox.snapshot_k8s_volume_snapshot_name:
            self._clear_snapshot_binding(sandbox)
            self.session.add(sandbox)

    async def _create_restored_sandbox(self, sandbox: Sandbox, *, replicas: int) -> None:
        template = await self._resolve_template(sandbox.k8s_namespace, sandbox.template)
        image = template.get("image", "")
        if not image:
            raise TemplateNotFoundError(sandbox.template)

        resource_requests = template["resource_spec"]
        resources = {
            "requests": resource_requests,
            "limits": _effective_resource_limits(resource_requests, template.get("resource_limits")),
        }
        labels = {
            LABEL_SANDBOX_ID: sandbox.id,
            LABEL_OWNER_ID: sandbox.owner_id,
            LABEL_TEMPLATE: sandbox.template,
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        }
        pod_labels = {
            LABEL_SANDBOX_ID: sandbox.id,
            LABEL_OWNER_ID: sandbox.owner_id,
            LABEL_WORKLOAD: WORKLOAD_SANDBOX,
            LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        }
        volume_claim_templates = [
            {
                "metadata": {
                    "name": STORAGE_ROLE_WORKSPACE,
                    "labels": _workspace_labels(sandbox),
                },
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": settings.sandbox_storage_class,
                    "resources": {"requests": {"storage": sandbox.storage_size}},
                    "dataSource": {
                        "name": sandbox.snapshot_k8s_volume_snapshot_name,
                        "kind": "VolumeSnapshot",
                        "apiGroup": SNAPSHOT_API_GROUP,
                    },
                },
            }
        ]

        await self.k8s.create_sandbox(
            name=sandbox.k8s_sandbox_name or sandbox.id,
            namespace=sandbox.k8s_namespace,
            image=image,
            container_port=settings.sandbox_port,
            resources=resources,
            replicas=replicas,
            startup_probe=template.get("startup_probe"),
            readiness_probe=template.get("readiness_probe"),
            liveness_probe=template.get("liveness_probe"),
            volume_claim_templates=volume_claim_templates,
            labels=labels,
            annotations={
                ANNOTATION_SANDBOX_NAME: sandbox.name,
                ANNOTATION_CREATED_AT: sandbox.gmt_created.isoformat(),
            },
            pod_labels=pod_labels,
        )

    async def _resolve_template(self, namespace: str, template_name: str) -> dict:
        templates = await self.k8s.list_sandbox_templates(namespace=namespace)
        template = next((item for item in templates if item["name"] == template_name), None)
        if template is None:
            raise TemplateNotFoundError(template_name)
        return template

    async def _release_live_workspace_assets(self, sandbox: Sandbox) -> None:
        cr_name = sandbox.k8s_sandbox_name or sandbox.id
        cr = await self.k8s.get_sandbox(cr_name, sandbox.k8s_namespace)
        if cr is not None:
            await self.k8s.delete_sandbox(cr_name, sandbox.k8s_namespace)

        if sandbox.k8s_workspace_pvc_name is None:
            await self._refresh_workspace_binding(sandbox)
        if sandbox.k8s_workspace_pvc_name:
            pvc = await self.k8s.get_persistent_volume_claim(sandbox.k8s_workspace_pvc_name, sandbox.k8s_namespace)
            if pvc is not None:
                await self.k8s.delete_persistent_volume_claim(sandbox.k8s_workspace_pvc_name, sandbox.k8s_namespace)

    async def _refresh_workspace_binding(self, sandbox: Sandbox) -> bool:
        discovery_strategy = "label_selector"
        pvcs = await self.k8s.list_persistent_volume_claims(
            sandbox.k8s_namespace,
            labels={LABEL_SANDBOX_ID: sandbox.id, LABEL_STORAGE_ROLE: STORAGE_ROLE_WORKSPACE},
        )
        pvc = _choose_workspace_pvc(pvcs)
        if pvc is None:
            for candidate_name in _workspace_pvc_candidate_names(sandbox):
                pvc = await self.k8s.get_persistent_volume_claim(candidate_name, sandbox.k8s_namespace)
                if pvc is not None:
                    discovery_strategy = f"name:{candidate_name}"
                    break
        if pvc is None:
            all_pvcs = await self.k8s.list_persistent_volume_claims(sandbox.k8s_namespace)
            pvc = _choose_workspace_pvc([item for item in all_pvcs if _pvc_owned_by_sandbox(item, sandbox)])
            if pvc is not None:
                discovery_strategy = "owner_reference"
        if pvc is None:
            logger.warning(
                "Workspace PVC discovery failed for sandbox %s in namespace %s (known_pvc=%s candidates=%s)",
                sandbox.id,
                sandbox.k8s_namespace,
                sandbox.k8s_workspace_pvc_name,
                _workspace_pvc_candidate_names(sandbox),
            )
            return False

        sandbox.k8s_workspace_pvc_name = pvc.get("metadata", {}).get("name")
        pv_name = pvc.get("spec", {}).get("volumeName")
        sandbox.k8s_workspace_pv_name = pv_name

        if pv_name:
            pv = await self.k8s.get_persistent_volume(pv_name)
            if pv is not None:
                sandbox.workspace_volume_handle = pv.get("spec", {}).get("csi", {}).get("volumeHandle")
                sandbox.workspace_zone = _extract_zone_from_pv(pv)

        if discovery_strategy != "label_selector":
            logger.info(
                "Resolved workspace PVC for sandbox %s via %s (pvc=%s pv=%s)",
                sandbox.id,
                discovery_strategy,
                sandbox.k8s_workspace_pvc_name,
                sandbox.k8s_workspace_pv_name,
            )

        self.session.add(sandbox)
        return True

    async def _fail_snapshot(self, sandbox: Sandbox, message: str) -> None:
        logger.warning("Cold snapshot failed for sandbox %s: %s", sandbox.id, message)
        sandbox.pending_operation = None
        sandbox.status = SandboxStatus.STOPPED
        sandbox.storage_backend_mode = sandbox.storage_backend_mode or StorageBackendMode.LIVE_DISK
        sandbox.status_message = message
        self.session.add(sandbox)

    async def _fail_restore(self, sandbox: Sandbox, message: str) -> None:
        logger.warning("Cold restore failed for sandbox %s: %s", sandbox.id, message)
        sandbox.pending_operation = None
        sandbox.status = SandboxStatus.COLD
        sandbox.storage_backend_mode = sandbox.storage_backend_mode or StorageBackendMode.STANDARD_SNAPSHOT
        sandbox.status_message = message
        self.session.add(sandbox)

    def _clear_snapshot_binding(self, sandbox: Sandbox) -> None:
        sandbox.gmt_snapshotted = None
        sandbox.snapshot_provider_id = None
        sandbox.snapshot_k8s_volume_snapshot_name = None
        sandbox.snapshot_k8s_volume_snapshot_content_name = None


async def run_storage_snapshot_tick(
    session_factory: async_sessionmaker[AsyncSession],
    k8s_client: K8sClientProtocol | None = None,
) -> None:
    async with session_factory() as session:
        result = await session.execute(
            select(Sandbox.id).where(
                Sandbox.gmt_deleted.is_(None),
                Sandbox.pending_operation.in_(
                    [SandboxPendingOperation.SNAPSHOTTING, SandboxPendingOperation.RESTORING]
                ),
            )
        )
        sandbox_ids = list(result.scalars().all())

    if not sandbox_ids:
        return

    k8s = k8s_client or get_k8s_client()
    for sandbox_id in sandbox_ids:
        async with session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            if sandbox is None or sandbox.pending_operation is None or sandbox.gmt_deleted is not None:
                continue
            orchestrator = StorageSnapshotOrchestrator(session=session, k8s_client=k8s)
            try:
                await orchestrator.process_sandbox(sandbox)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Storage snapshot tick failed for sandbox %s", sandbox_id)


def _snapshot_name(sandbox_id: str) -> str:
    return f"{sandbox_id}-workspace-snapshot"


def _workspace_labels(sandbox: Sandbox) -> dict[str, str]:
    return {
        LABEL_SANDBOX_ID: sandbox.id,
        LABEL_OWNER_ID: sandbox.owner_id,
        LABEL_TEMPLATE: sandbox.template,
        LABEL_PROVISION_MODE: PROVISION_MODE_DIRECT,
        LABEL_WORKLOAD: WORKLOAD_SANDBOX,
        LABEL_STORAGE_ROLE: STORAGE_ROLE_WORKSPACE,
    }


def _effective_resource_limits(requests: dict[str, str], limits: dict[str, str] | None) -> dict[str, str]:
    if not limits:
        return requests
    cpu, mem = limits.get("cpu", "").strip(), limits.get("memory", "").strip()
    if cpu and mem:
        return {"cpu": cpu, "memory": mem}
    return requests


def _choose_workspace_pvc(pvcs: Sequence[dict]) -> dict | None:
    if not pvcs:
        return None
    return sorted(pvcs, key=lambda pvc: pvc.get("metadata", {}).get("name", ""))[0]


def _workspace_pvc_candidate_names(sandbox: Sandbox) -> list[str]:
    names: list[str] = []
    for candidate in (
        sandbox.k8s_workspace_pvc_name,
        f"{STORAGE_ROLE_WORKSPACE}-{sandbox.k8s_sandbox_name or sandbox.id}",
        f"{STORAGE_ROLE_WORKSPACE}-{sandbox.id}",
        f"{sandbox.k8s_sandbox_name or sandbox.id}-{STORAGE_ROLE_WORKSPACE}",
        f"{sandbox.id}-{STORAGE_ROLE_WORKSPACE}",
    ):
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _pvc_owned_by_sandbox(pvc: dict, sandbox: Sandbox) -> bool:
    expected_names = {sandbox.id}
    if sandbox.k8s_sandbox_name:
        expected_names.add(sandbox.k8s_sandbox_name)
    owner_refs = pvc.get("metadata", {}).get("ownerReferences", [])
    for owner_ref in owner_refs:
        if owner_ref.get("kind") == "Sandbox" and owner_ref.get("name") in expected_names:
            return True
    return False


def _extract_zone_from_pv(pv: dict) -> str | None:
    terms = pv.get("spec", {}).get("nodeAffinity", {}).get("required", {}).get("nodeSelectorTerms", [])
    for term in terms:
        for expr in term.get("matchExpressions", []):
            if "zone" in expr.get("key", ""):
                values = expr.get("values", [])
                if values:
                    return values[0]
    return None
