"""Sandbox lifecycle service layer.

Dual-path provisioning:
- persist=False → SandboxClaim path (WarmPool-eligible, no storage)
- persist=True  → Direct Sandbox CR path (with volumeClaimTemplates)

start/stop use scale_sandbox on the Sandbox CR regardless of path.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.config import settings
from treadstone.core.errors import (
    InvalidTransitionError,
    SandboxDurationExceededError,
    SandboxNameConflictError,
    SandboxNotFoundError,
    StorageBackendNotReadyError,
    TemplateNotFoundError,
)
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import random_id, utc_now
from treadstone.services.k8s_client import K8sClientProtocol, get_k8s_client
from treadstone.services.metering_helpers import parse_storage_size_gib

if TYPE_CHECKING:
    from treadstone.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

_RESOURCE_LIMITS_MULTIPLIER = 2


def _build_resource_limits(requests: dict[str, str]) -> dict[str, str]:
    """Derive resource limits from requests (2x multiplier for CPU, same ratio for memory)."""
    limits: dict[str, str] = {}
    cpu = requests.get("cpu", "")
    if cpu.endswith("m"):
        limits["cpu"] = f"{int(cpu[:-1]) * _RESOURCE_LIMITS_MULTIPLIER}m"
    elif cpu:
        limits["cpu"] = str(int(cpu) * _RESOURCE_LIMITS_MULTIPLIER)
    mem = requests.get("memory", "")
    if mem.endswith("Mi"):
        val = int(mem[:-2]) * _RESOURCE_LIMITS_MULTIPLIER
        limits["memory"] = f"{val}Mi" if val < 1024 else f"{val // 1024}Gi"
    elif mem.endswith("Gi"):
        limits["memory"] = f"{int(mem[:-2]) * _RESOURCE_LIMITS_MULTIPLIER}Gi"
    return limits


class SandboxService:
    def __init__(
        self,
        session: AsyncSession,
        k8s_client: K8sClientProtocol | None = None,
        metering: MeteringService | None = None,
    ):
        self.session = session
        self.k8s = k8s_client or get_k8s_client()
        self._metering = metering

    async def create(
        self,
        owner_id: str,
        template: str,
        name: str | None = None,
        labels: dict | None = None,
        auto_stop_interval: int = 15,
        auto_delete_interval: int = -1,
        persist: bool = False,
        storage_size: str | None = None,
    ) -> Sandbox:
        effective_storage_size = storage_size or settings.sandbox_default_storage_size

        # ── Metering: quota checks (must run before any resource creation) ──
        if self._metering is not None:
            await self._metering.check_template_allowed(self.session, owner_id, template)
            await self._metering.check_compute_quota(self.session, owner_id)
            await self._metering.check_concurrent_limit(self.session, owner_id)

            if persist:
                size_gib = parse_storage_size_gib(effective_storage_size)
                await self._metering.check_storage_quota(self.session, owner_id, size_gib)

            max_duration = await self._metering.check_sandbox_duration(self.session, owner_id)
            if auto_stop_interval > 0 and (auto_stop_interval * 60) > max_duration:
                plan = await self._metering.get_user_plan(self.session, owner_id)
                raise SandboxDurationExceededError(plan.tier, max_duration)

        # ── Create sandbox record ──
        sandbox_id = "sb" + random_id()
        sandbox_name = name or f"sb-{random_id(8)}"

        if persist:
            await self._ensure_persistent_storage_backend_ready()

        sandbox = Sandbox()
        sandbox.id = sandbox_id
        sandbox.name = sandbox_name
        sandbox.owner_id = owner_id
        sandbox.template = template
        sandbox.labels = labels or {}
        sandbox.auto_stop_interval = auto_stop_interval
        sandbox.auto_delete_interval = auto_delete_interval
        sandbox.status = SandboxStatus.CREATING
        sandbox.version = 1
        sandbox.endpoints = {}
        sandbox.gmt_created = utc_now()
        sandbox.k8s_namespace = settings.sandbox_namespace
        sandbox.persist = persist
        sandbox.storage_size = effective_storage_size if persist else None

        if persist:
            sandbox.provision_mode = "direct"
            sandbox.k8s_sandbox_name = sandbox_id
        else:
            sandbox.provision_mode = "claim"
            sandbox.k8s_sandbox_claim_name = sandbox_id

        self.session.add(sandbox)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise SandboxNameConflictError(sandbox_name)
        await self.session.refresh(sandbox)

        try:
            if persist:
                await self._create_direct(sandbox, template, effective_storage_size)
            else:
                await self._create_via_claim(sandbox, template)
        except TemplateNotFoundError:
            await self.session.delete(sandbox)
            await self.session.commit()
            raise
        except Exception:
            logger.exception("Failed to create K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = f"Failed to create {'Sandbox CR' if persist else 'SandboxClaim'}"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

        # ── Metering: record storage allocation for persistent sandboxes (best-effort) ──
        if self._metering is not None and persist and sandbox.status != SandboxStatus.ERROR:
            try:
                size_gib = parse_storage_size_gib(effective_storage_size)
                await self._metering.record_storage_allocation(self.session, owner_id, sandbox.id, size_gib)
                await self.session.commit()
            except Exception:
                logger.exception("Failed to record storage allocation for sandbox %s", sandbox_id)

        return sandbox

    async def _resolve_template(self, namespace: str, template: str) -> dict:
        templates = await self.k8s.list_sandbox_templates(namespace=namespace)
        tmpl = next((t for t in templates if t["name"] == template), None)
        if tmpl is None:
            raise TemplateNotFoundError(template)
        return tmpl

    async def _create_via_claim(self, sandbox: Sandbox, template: str) -> None:
        await self._resolve_template(sandbox.k8s_namespace, template)

        claim_name = sandbox.k8s_sandbox_claim_name or sandbox.id
        logger.info("Creating SandboxClaim %s (template=%s, ns=%s)", claim_name, template, sandbox.k8s_namespace)
        await self.k8s.create_sandbox_claim(
            name=claim_name,
            template_ref=template,
            namespace=sandbox.k8s_namespace,
        )

    async def _ensure_persistent_storage_backend_ready(self) -> None:
        storage_class_name = settings.sandbox_storage_class.strip()
        storage_class = await self.k8s.get_storage_class(storage_class_name)
        if storage_class is None:
            raise StorageBackendNotReadyError(storage_class_name)

    async def _create_direct(self, sandbox: Sandbox, template: str, storage_size: str) -> None:
        tmpl = await self._resolve_template(sandbox.k8s_namespace, template)

        image = tmpl.get("image", "")
        if not image:
            raise TemplateNotFoundError(template)

        resource_requests = tmpl["resource_spec"]
        resources = {
            "requests": resource_requests,
            "limits": _build_resource_limits(resource_requests),
        }
        volume_claim_templates = [
            {
                "metadata": {"name": "workspace"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "storageClassName": settings.sandbox_storage_class,
                    "resources": {"requests": {"storage": storage_size}},
                },
            }
        ]

        k8s_name = sandbox.k8s_sandbox_name or sandbox.id
        logger.info(
            "Creating Sandbox CR %s (template=%s, persist=true, ns=%s)", k8s_name, template, sandbox.k8s_namespace
        )
        await self.k8s.create_sandbox(
            name=k8s_name,
            namespace=sandbox.k8s_namespace,
            image=image,
            container_port=settings.sandbox_port,
            resources=resources,
            volume_claim_templates=volume_claim_templates,
        )

    async def get(self, sandbox_id: str, owner_id: str) -> Sandbox | None:
        result = await self.session.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: str, labels: dict | None = None) -> list[Sandbox]:
        stmt = select(Sandbox).where(Sandbox.owner_id == owner_id)
        result = await self.session.execute(stmt)
        sandboxes = list(result.scalars().all())

        if labels:
            sandboxes = [s for s in sandboxes if all(s.labels.get(k) == v for k, v in labels.items())]

        return sandboxes

    async def delete(self, sandbox_id: str, owner_id: str) -> None:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if not is_valid_transition(sandbox.status, SandboxStatus.DELETING):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "deleting")

        # ── Metering: release storage before K8s deletion (best-effort) ──
        if self._metering is not None and sandbox.persist:
            try:
                await self._metering.record_storage_release(self.session, sandbox.id)
            except Exception:
                logger.exception("Failed to release storage metering for sandbox %s", sandbox_id)

        sandbox.status = SandboxStatus.DELETING
        sandbox.version += 1
        self.session.add(sandbox)

        link_result = await self.session.execute(
            select(SandboxWebLink).where(
                SandboxWebLink.sandbox_id == sandbox.id,
                SandboxWebLink.gmt_deleted.is_(None),
            )
        )
        link = link_result.scalar_one_or_none()
        if link is not None:
            link.gmt_deleted = utc_now()
            link.gmt_updated = utc_now()
            self.session.add(link)
        await self.session.commit()

        try:
            if sandbox.provision_mode == "direct":
                sb_name = sandbox.k8s_sandbox_name or sandbox.id
                logger.info("Deleting Sandbox CR %s (ns=%s)", sb_name, sandbox.k8s_namespace)
                await self.k8s.delete_sandbox(name=sb_name, namespace=sandbox.k8s_namespace)
            else:
                claim_name = sandbox.k8s_sandbox_claim_name or sandbox.id
                logger.info("Deleting SandboxClaim %s (ns=%s)", claim_name, sandbox.k8s_namespace)
                await self.k8s.delete_sandbox_claim(name=claim_name, namespace=sandbox.k8s_namespace)
        except Exception:
            logger.exception("Failed to delete K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to delete K8s resource"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

    async def start(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status != SandboxStatus.STOPPED:
            raise InvalidTransitionError(sandbox_id, sandbox.status, "ready")

        # ── Metering: quota checks before resuming ──
        if self._metering is not None:
            await self._metering.check_compute_quota(self.session, owner_id)
            await self._metering.check_concurrent_limit(self.session, owner_id)

        sandbox.status = SandboxStatus.CREATING
        sandbox.gmt_started = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
        try:
            logger.info("Scaling sandbox %s to replicas=1 (ns=%s)", k8s_name, sandbox.k8s_namespace)
            await self.k8s.scale_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace, replicas=1)
        except Exception:
            logger.exception("Failed to scale sandbox %s to 1", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to start sandbox"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

        return sandbox

    async def stop(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status not in (SandboxStatus.READY, SandboxStatus.ERROR):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "stopped")

        sandbox.status = SandboxStatus.STOPPED
        sandbox.gmt_stopped = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id
        try:
            logger.info("Scaling sandbox %s to replicas=0 (ns=%s)", k8s_name, sandbox.k8s_namespace)
            await self.k8s.scale_sandbox(name=k8s_name, namespace=sandbox.k8s_namespace, replicas=0)
        except Exception:
            logger.exception("Failed to scale sandbox %s to 0", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to stop sandbox"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

        return sandbox
