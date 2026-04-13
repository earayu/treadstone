"""Admin API — sandbox operations endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.audit.services.audit import record_audit_event
from treadstone.core.database import get_session
from treadstone.core.errors import ConflictError, NotFoundError
from treadstone.identity.api.deps import get_current_admin
from treadstone.identity.models.user import User
from treadstone.sandbox.models.sandbox import Sandbox, SandboxPendingOperation, SandboxStatus

router = APIRouter()


@router.post("/sandboxes/{sandbox_id}/force-reset-pending")
async def admin_force_reset_pending(
    sandbox_id: str,
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Force-clear a stuck ``pending_operation`` on a sandbox.

    Currently only supports resetting ``snapshotting``.  Restoring operations
    may have already materialized K8s resources (Sandbox CR, PVC) which cannot
    be safely cleaned up by a simple status reset; those require manual
    intervention or waiting for the restore to converge.
    """
    sandbox = await session.get(Sandbox, sandbox_id)
    if sandbox is None or sandbox.gmt_deleted is not None:
        raise NotFoundError("Sandbox", sandbox_id)

    if sandbox.pending_operation is None:
        return {
            "id": sandbox.id,
            "status": sandbox.status,
            "pending_operation": None,
            "message": "No-op: no pending operation to reset.",
        }

    if sandbox.pending_operation != SandboxPendingOperation.SNAPSHOTTING:
        raise ConflictError(
            f"Only 'snapshotting' can be force-reset. "
            f"This sandbox has pending_operation={sandbox.pending_operation!r} which may have "
            f"materialized K8s resources that require manual cleanup."
        )

    prev_pending = sandbox.pending_operation
    prev_status = sandbox.status

    sandbox.pending_operation = None
    sandbox.status = SandboxStatus.STOPPED
    sandbox.status_message = f"Force-reset by admin from pending_operation={prev_pending}"
    sandbox.version += 1
    session.add(sandbox)

    await record_audit_event(
        session,
        action="admin.sandbox.force_reset_pending",
        target_type="sandbox",
        target_id=sandbox_id,
        actor_user_id=admin.id,
        metadata={
            "previous_status": prev_status,
            "previous_pending_operation": prev_pending,
            "new_status": sandbox.status,
            "owner_id": sandbox.owner_id,
        },
        request=request,
    )
    await session.commit()

    return {
        "id": sandbox.id,
        "status": sandbox.status,
        "pending_operation": sandbox.pending_operation,
        "message": f"Reset pending_operation={prev_pending}; status {prev_status} -> {sandbox.status}",
    }
