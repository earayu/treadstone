"""Sandbox proxy API router — transparent HTTP and WebSocket reverse proxy to sandbox pods."""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Depends, Request, WebSocket
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import _authenticate_api_key_value, get_current_data_plane_user
from treadstone.config import settings
from treadstone.core.database import async_session, get_session
from treadstone.core.errors import (
    SandboxNotFoundError,
    SandboxNotReadyError,
    SandboxUnreachableError,
)
from treadstone.core.request_context import set_scope_context
from treadstone.models.api_key import ApiKeyDataPlaneMode, ApiKeySandboxGrant
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.user import User, utc_now
from treadstone.services.sandbox_proxy import proxy_http_request, proxy_websocket

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

    headers = dict(request.headers)
    k8s_id = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id

    body = await request.body()

    # Preserve the query string so MCP SSE params (e.g. ?sessionId=…) reach the sandbox.
    query_string = request.url.query
    full_path = f"{path}?{query_string}" if query_string else path

    try:
        status_code, resp_headers, resp = await proxy_http_request(
            method=request.method,
            sandbox_id=k8s_id,
            path=full_path,
            headers=headers,
            body=body,
            namespace=sandbox.k8s_namespace,
            port=settings.sandbox_port,
        )
    except Exception:
        logger.exception("Proxy failed for sandbox %s", sandbox_id)
        raise SandboxUnreachableError(sandbox_id)

    from sqlalchemy import update as sa_update

    await session.execute(sa_update(Sandbox).where(Sandbox.id == sandbox_id).values(gmt_last_active=utc_now()))
    await session.commit()

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=status_code,
        headers=resp_headers,
    )


@router.websocket("/{sandbox_id}/proxy/{path:path}")
async def ws_proxy(
    websocket: WebSocket,
    sandbox_id: str,
    path: str,
) -> None:
    """WebSocket proxy to sandbox pods, authenticated via API Key.

    The key may be supplied as:
    - ``Authorization: Bearer sk-…`` header (preferred)
    - ``?token=sk-…`` query param (for clients that cannot set WS headers)

    Upstream namespace and port match the HTTP proxy (sandbox row + settings).
    """
    auth_header = websocket.headers.get("authorization", "")
    token_param = websocket.query_params.get("token", "")

    secret: str | None = None
    if auth_header.lower().startswith("bearer "):
        candidate = auth_header[7:]
        if candidate.startswith("sk-"):
            secret = candidate
    if secret is None and token_param.startswith("sk-"):
        secret = token_param

    if not secret:
        await websocket.close(code=1008, reason="API Key required.")
        return

    async with async_session() as session:
        auth_result = await _authenticate_api_key_value(session, secret)
        if auth_result is None:
            await websocket.close(code=1008, reason="Invalid or expired API key.")
            return

        api_key, user = auth_result
        if api_key.data_plane_mode == ApiKeyDataPlaneMode.NONE.value:
            await websocket.close(code=1008, reason="This API key does not have data plane access.")
            return

        if api_key.data_plane_mode == ApiKeyDataPlaneMode.SELECTED.value:
            grant_result = await session.execute(
                select(ApiKeySandboxGrant.sandbox_id).where(
                    ApiKeySandboxGrant.api_key_id == api_key.id,
                    ApiKeySandboxGrant.sandbox_id == sandbox_id,
                )
            )
            if grant_result.scalar_one_or_none() is None:
                await websocket.close(code=1008, reason="This API key does not have access to this sandbox.")
                return

        sb_result = await session.execute(
            select(Sandbox).where(
                Sandbox.id == sandbox_id,
                Sandbox.owner_id == user.id,
                Sandbox.gmt_deleted.is_(None),
            )
        )
        sandbox = sb_result.scalar_one_or_none()
        if sandbox is None:
            await websocket.close(code=1008, reason="Sandbox not found.")
            return

        if sandbox.status != SandboxStatus.READY.value:
            await websocket.close(code=1008, reason="Sandbox is not ready.")
            return

    # Populate structured request context for audit logging (mirrors HTTP proxy).
    set_scope_context(
        websocket.scope,
        credential_type="api_key",
        actor_user_id=user.id,
        actor_api_key_id=api_key.id,
        sandbox_id=sandbox_id,
        route_kind="ws_proxy",
    )

    await websocket.accept()

    # Build upstream path; strip the token param we consumed for auth.
    query_string = websocket.url.query
    if token_param:
        params = [(k, v) for k, v in parse_qsl(query_string) if k != "token"]
        full_path = f"{path}?{urlencode(params)}" if params else path
    else:
        full_path = f"{path}?{query_string}" if query_string else path

    k8s_id = sandbox.k8s_sandbox_name or sandbox.k8s_sandbox_claim_name or sandbox.id

    async def _touch_activity() -> None:
        async with async_session() as touch_session:
            from sqlalchemy import update as sa_update

            await touch_session.execute(
                sa_update(Sandbox).where(Sandbox.id == sandbox_id).values(gmt_last_active=utc_now())
            )
            await touch_session.commit()

    try:
        await proxy_websocket(
            client_ws=websocket,
            sandbox_id=k8s_id,
            path=full_path,
            namespace=sandbox.k8s_namespace,
            port=settings.sandbox_port,
            on_activity=_touch_activity,
        )
    except Exception:
        logger.exception("WebSocket proxy failed for sandbox %s", sandbox_id)
        try:
            await websocket.close(code=1011, reason="Upstream connection failed.")
        except RuntimeError:
            pass
