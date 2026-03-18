"""
Sandbox proxy API router — HTTP only.

Provides transparent HTTP reverse proxying to sandbox pods for Agent SDK use.
sandbox_id is taken from the URL path; namespace and port can be overridden
per-request via X-Sandbox-Namespace / X-Sandbox-Port headers.

  /api/sandbox/{sandbox_id}/{path}

WebSocket proxying (e.g. VNC) is handled by SandboxSubdomainMiddleware,
not this router.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from treadstone.services.sandbox_proxy import (
    proxy_http_request,
    resolve_routing,
)

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.api_route(
    "/{sandbox_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def http_proxy_by_path(request: Request, sandbox_id: str, path: str) -> StreamingResponse:
    headers = dict(request.headers)
    try:
        routing = resolve_routing(headers, path_sandbox_id=sandbox_id)
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
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to the backend sandbox: {routing['sandbox_id']}",
        ) from exc

    return StreamingResponse(
        content=resp.aiter_bytes(),
        status_code=status_code,
        headers=resp_headers,
    )
