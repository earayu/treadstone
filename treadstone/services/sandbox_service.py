"""Sandbox lifecycle service layer.

Dual-path provisioning:
- persist=False → SandboxClaim path (WarmPool-eligible, no storage)
- persist=True  → Direct Sandbox CR path (with volumeClaimTemplates)

start/stop use scale_sandbox on the Sandbox CR regardless of path.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.config import settings
from treadstone.core.errors import InvalidTransitionError, SandboxNotFoundError, TemplateNotFoundError
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.models.user import random_id, utc_now
from treadstone.services.k8s_client import K8sClientProtocol, get_k8s_client

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
    def __init__(self, session: AsyncSession, k8s_client: K8sClientProtocol | None = None):
        self.session = session
        self.k8s = k8s_client or get_k8s_client()

    async def create(
        self,
        owner_id: str,
        template: str,
        name: str | None = None,
        runtime_type: str = "aio",
        labels: dict | None = None,
        auto_stop_interval: int = 15,
        auto_delete_interval: int = -1,
        persist: bool = False,
        storage_size: str = "10Gi",
    ) -> Sandbox:
        sandbox_id = "sb" + random_id()
        sandbox_name = name or f"sb-{random_id(8)}"

        sandbox = Sandbox()
        sandbox.id = sandbox_id
        sandbox.name = sandbox_name
        sandbox.owner_id = owner_id
        sandbox.template = template
        sandbox.runtime_type = runtime_type
        sandbox.labels = labels or {}
        sandbox.auto_stop_interval = auto_stop_interval
        sandbox.auto_delete_interval = auto_delete_interval
        sandbox.status = SandboxStatus.CREATING
        sandbox.version = 1
        sandbox.endpoints = {}
        sandbox.gmt_created = utc_now()
        sandbox.k8s_namespace = settings.sandbox_namespace
        sandbox.persist = persist
        sandbox.storage_size = storage_size if persist else None

        if persist:
            sandbox.provision_mode = "direct"
            sandbox.k8s_sandbox_name = sandbox_name
        else:
            sandbox.provision_mode = "claim"
            sandbox.k8s_sandbox_claim_name = sandbox_name

        self.session.add(sandbox)
        await self.session.commit()
        await self.session.refresh(sandbox)

        try:
            if persist:
                await self._create_direct(sandbox, template, storage_size)
            else:
                await self._create_via_claim(sandbox, template)
        except Exception:
            logger.exception("Failed to create K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = f"Failed to create {'Sandbox CR' if persist else 'SandboxClaim'}"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

        return sandbox

    async def _create_via_claim(self, sandbox: Sandbox, template: str) -> None:
        logger.info("Creating SandboxClaim %s (template=%s, ns=%s)", sandbox.name, template, sandbox.k8s_namespace)
        await self.k8s.create_sandbox_claim(
            name=sandbox.name,
            template_ref=template,
            namespace=sandbox.k8s_namespace,
        )

    async def _create_direct(self, sandbox: Sandbox, template: str, storage_size: str) -> None:
        templates = await self.k8s.list_sandbox_templates(namespace=sandbox.k8s_namespace)
        tmpl = next((t for t in templates if t["name"] == template), None)
        if tmpl is None:
            raise TemplateNotFoundError(template)

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
                    "resources": {"requests": {"storage": storage_size}},
                },
            }
        ]

        logger.info(
            "Creating Sandbox CR %s (template=%s, persist=true, ns=%s)", sandbox.name, template, sandbox.k8s_namespace
        )
        await self.k8s.create_sandbox(
            name=sandbox.name,
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
        stmt = select(Sandbox).where(
            Sandbox.owner_id == owner_id,
            Sandbox.status != SandboxStatus.DELETED,
        )
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

        sandbox.status = SandboxStatus.DELETING
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        try:
            if sandbox.provision_mode == "direct":
                sb_name = sandbox.k8s_sandbox_name or sandbox.name
                logger.info("Deleting Sandbox CR %s (ns=%s)", sb_name, sandbox.k8s_namespace)
                await self.k8s.delete_sandbox(name=sb_name, namespace=sandbox.k8s_namespace)
            else:
                claim_name = sandbox.k8s_sandbox_claim_name or sandbox.name
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

        sandbox.status = SandboxStatus.CREATING
        sandbox.gmt_started = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.name
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

        k8s_name = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.name
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
