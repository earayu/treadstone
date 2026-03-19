"""
Sandbox proxy API router — transparent HTTP reverse proxy to sandbox pods.

Requires authentication and verifies sandbox ownership + ready status before proxying.

  /v1/sandboxes/{sandbox_id}/proxy/{path}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_user
from treadstone.core.database import get_session
from treadstone.core.errors import SandboxNotFoundError, SandboxNotReadyError, SandboxUnreachableError
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import User
from treadstone.services.sandbox_proxy import (
    proxy_http_request,
    resolve_routing,
)

router = APIRouter(prefix="/v1/sandboxes", tags=["sandbox-proxy"])


@router.api_route(
    "/{sandbox_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def http_proxy(
    request: Request,
    sandbox_id: str,
    path: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    result = await session.execute(select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.owner_id == user.id))
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)

    if sandbox.status not in (SandboxStatus.READY, SandboxStatus.CREATING):
        raise SandboxNotReadyError(sandbox_id, sandbox.status)

    headers = dict(request.headers)
    try:
        routing = resolve_routing(headers, path_sandbox_id=sandbox.k8s_sandbox_name or sandbox.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    body = await request.body()

    try:
        status_code, resp_headers, resp = await proxy_http_request(
            method=request.method,
            sandbox_id=routing["sandbox_id"],
            path=path,
            headers=headers,
            body=body,
            namespace=routing["namespace"],
            port=routing["port"],
        )
    except Exception:
        raise SandboxUnreachableError(sandbox_id)

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=status_code,
        headers=resp_headers,
    )
