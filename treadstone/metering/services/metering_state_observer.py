"""MeteringStateObserver — SandboxStateObserver implementation backed by MeteringService.

Provides the concrete metering side-effects (open/close compute sessions,
release storage ledgers) that fire when the K8s sync loop detects sandbox
lifecycle transitions.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.metering.services.metering_service import MeteringService

logger = logging.getLogger(__name__)

__all__ = ["MeteringStateObserver"]


class MeteringStateObserver:
    """Observe sandbox state transitions and apply metering side-effects.

    Satisfies the ``SandboxStateObserver`` Protocol defined in
    ``treadstone.infra.services.sandbox_state_observer``.
    """

    def __init__(self, metering: MeteringService | None = None) -> None:
        self._metering = metering or MeteringService()

    async def on_sandbox_ready(
        self,
        session: AsyncSession,
        sandbox_id: str,
        owner_id: str,
        template: str,
    ) -> None:
        """Open a ComputeSession when a sandbox becomes READY."""
        await self._metering.open_compute_session(session, sandbox_id, owner_id, template)

    async def on_sandbox_stopped(
        self,
        session: AsyncSession,
        sandbox_id: str,
    ) -> None:
        """Close any open ComputeSession when a sandbox leaves READY."""
        await self._metering.close_compute_session(session, sandbox_id)

    async def on_sandbox_deleted(
        self,
        session: AsyncSession,
        sandbox_id: str,
        persist: bool,
    ) -> None:
        """Close compute session and optionally release storage ledger on deletion."""
        await self._metering.close_compute_session(session, sandbox_id)
        if persist:
            await self._metering.record_storage_release(session, sandbox_id)
