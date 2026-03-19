"""Sandbox lifecycle service layer.

Handles create/get/list/delete/start/stop with state machine validation
and delegates K8s operations to an injected K8s client.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.core.errors import InvalidTransitionError, SandboxNotFoundError
from treadstone.models.sandbox import Sandbox, SandboxStatus, is_valid_transition
from treadstone.models.user import random_id, utc_now
from treadstone.services.k8s_client import K8sClientProtocol, get_k8s_client

logger = logging.getLogger(__name__)


class SandboxService:
    def __init__(self, session: AsyncSession, k8s_client: K8sClientProtocol | None = None):
        self.session = session
        self.k8s = k8s_client or get_k8s_client()

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

        try:
            await self.k8s.create_sandbox_cr(
                name=sandbox_name,
                template=template,
                namespace=sandbox.k8s_namespace,
                image=image,
            )
        except Exception:
            logger.exception("Failed to create K8s resource for sandbox %s", sandbox_id)
            sandbox.status = SandboxStatus.ERROR
            sandbox.status_message = "Failed to create K8s resource"
            sandbox.version += 1
            self.session.add(sandbox)
            await self.session.commit()

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
            raise SandboxNotFoundError(sandbox_id)

        if not is_valid_transition(sandbox.status, SandboxStatus.DELETING):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "deleting")

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
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status != SandboxStatus.STOPPED:
            raise InvalidTransitionError(sandbox_id, sandbox.status, "ready")

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
            raise SandboxNotFoundError(sandbox_id)

        if sandbox.status not in (SandboxStatus.READY, SandboxStatus.ERROR):
            raise InvalidTransitionError(sandbox_id, sandbox.status, "stopped")

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
