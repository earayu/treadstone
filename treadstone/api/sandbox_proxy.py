"""Sandbox proxy API router — transparent HTTP reverse proxy to sandbox pods."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_data_plane_user
from treadstone.core.database import get_session
from treadstone.core.errors import (
    SandboxNotFoundError,
    SandboxNotReadyError,
    SandboxUnreachableError,
    ValidationError,
)
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import User, utc_now
from treadstone.services.sandbox_proxy import (
    proxy_http_request,
    resolve_routing,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sandboxes", tags=["sandbox-proxy"])


@router.api_route(
    "/{sandbox_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def http_proxy(
    request: Request,
    sandbox_id: str,
    path: str,
    user: User = Depends(get_current_data_plane_user),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    result = await session.execute(
        select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.owner_id == user.id, Sandbox.gmt_deleted.is_(None))
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)

    if sandbox.status != SandboxStatus.READY:
        raise SandboxNotReadyError(sandbox_id, sandbox.status)

    sandbox.gmt_last_active = utc_now()
    session.add(sandbox)
    await session.commit()

    headers = dict(request.headers)
    try:
        routing = resolve_routing(
            headers,
            path_sandbox_id=sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id,
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

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
        logger.exception("Proxy failed for sandbox %s", sandbox_id)
        raise SandboxUnreachableError(sandbox_id)

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=status_code,
        headers=resp_headers,
    )
