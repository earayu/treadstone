"""Sandbox lifecycle service layer.

Handles create/get/list/delete/start/stop with state machine validation
and delegates K8s operations to an injected K8s client.
"""

from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.models.user import random_id, utc_now


@runtime_checkable
class K8sClientProtocol(Protocol):
    async def create_sandbox_cr(self, name: str, template: str, namespace: str, image: str) -> dict: ...
    async def delete_sandbox_cr(self, name: str, namespace: str) -> bool: ...
    async def start_sandbox_cr(self, name: str, namespace: str) -> bool: ...
    async def stop_sandbox_cr(self, name: str, namespace: str) -> bool: ...


class FakeK8sClient:
    """Stub K8s client for testing — all operations succeed immediately."""

    async def create_sandbox_cr(self, name: str, template: str, namespace: str, image: str) -> dict:
        return {"metadata": {"name": name}}

    async def delete_sandbox_cr(self, name: str, namespace: str) -> bool:
        return True

    async def start_sandbox_cr(self, name: str, namespace: str) -> bool:
        return True

    async def stop_sandbox_cr(self, name: str, namespace: str) -> bool:
        return True


class SandboxService:
    def __init__(self, session: AsyncSession, k8s_client: K8sClientProtocol | None = None):
        self.session = session
        self.k8s = k8s_client or FakeK8sClient()

    async def create(
        self,
        owner_id: str,
        template: str,
        image: str,
        name: str | None = None,
        runtime_type: str = "aio",
        labels: dict | None = None,
        auto_stop_interval: int = 15,
        auto_delete_interval: int = -1,
    ) -> Sandbox:
        sandbox_id = "sb" + random_id()
        sandbox_name = name or f"sb-{random_id(8)}"

        sandbox = Sandbox()
        sandbox.id = sandbox_id
        sandbox.name = sandbox_name
        sandbox.owner_id = owner_id
        sandbox.template = template
        sandbox.runtime_type = runtime_type
        sandbox.image = image
        sandbox.labels = labels or {}
        sandbox.auto_stop_interval = auto_stop_interval
        sandbox.auto_delete_interval = auto_delete_interval
        sandbox.status = SandboxStatus.CREATING
        sandbox.version = 1
        sandbox.endpoints = {}
        sandbox.gmt_created = utc_now()
        sandbox.k8s_namespace = "treadstone"
        sandbox.k8s_sandbox_name = sandbox_name

        self.session.add(sandbox)
        await self.session.commit()
        await self.session.refresh(sandbox)

        await self.k8s.create_sandbox_cr(
            name=sandbox_name,
            template=template,
            namespace=sandbox.k8s_namespace,
            image=image,
        )

        return sandbox

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
            raise LookupError(f"Sandbox {sandbox_id} not found")

        if not is_valid_transition(sandbox.status, SandboxStatus.DELETING):
            raise ValueError(f"Invalid transition from {sandbox.status} to deleting")

        sandbox.status = SandboxStatus.DELETING
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        await self.k8s.delete_sandbox_cr(
            name=sandbox.k8s_sandbox_name or sandbox.name,
            namespace=sandbox.k8s_namespace,
        )

    async def start(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise LookupError(f"Sandbox {sandbox_id} not found")

        if sandbox.status != SandboxStatus.STOPPED:
            raise ValueError(f"Invalid transition from {sandbox.status} to ready — start requires stopped state")

        sandbox.status = SandboxStatus.READY
        sandbox.gmt_started = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        await self.k8s.start_sandbox_cr(
            name=sandbox.k8s_sandbox_name or sandbox.name,
            namespace=sandbox.k8s_namespace,
        )

        return sandbox

    async def stop(self, sandbox_id: str, owner_id: str) -> Sandbox:
        sandbox = await self.get(sandbox_id, owner_id)
        if sandbox is None:
            raise LookupError(f"Sandbox {sandbox_id} not found")

        if sandbox.status not in (SandboxStatus.READY, SandboxStatus.ERROR):
            raise ValueError(f"Invalid transition from {sandbox.status} to stopped — stop requires ready or error")

        sandbox.status = SandboxStatus.STOPPED
        sandbox.gmt_stopped = utc_now()
        sandbox.version += 1
        self.session.add(sandbox)
        await self.session.commit()

        await self.k8s.stop_sandbox_cr(
            name=sandbox.k8s_sandbox_name or sandbox.name,
            namespace=sandbox.k8s_namespace,
        )

        return sandbox
