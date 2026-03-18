"""
Sandbox proxy API router.

Provides transparent HTTP + WebSocket reverse proxying to sandbox pods.
sandbox_id is always taken from the URL path; namespace and port can be
overridden per-request via X-Sandbox-Namespace / X-Sandbox-Port headers.

  HTTP:      /api/sandbox/{sandbox_id}/{path}
  WebSocket: /api/sandbox/{sandbox_id}/ws/{path}

For browser Web UI access, use the subdomain-based route instead
(handled by SandboxSubdomainMiddleware, not this router).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from treadstone.services.sandbox_proxy import (
    proxy_http_request,
    proxy_websocket,
    resolve_routing,
)

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


# ── helpers ──────────────────────────────────────────────────────────────────


async def _do_http_proxy(
    request: Request,
    path: str,
    *,
    path_sandbox_id: str | None = None,
) -> StreamingResponse:
    headers = dict(request.headers)
    try:
        routing = resolve_routing(headers, path_sandbox_id=path_sandbox_id)
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


async def _do_ws_proxy(
    websocket: WebSocket,
    path: str,
    *,
    path_sandbox_id: str | None = None,
) -> None:
    headers = dict(websocket.headers)
    qp = dict(websocket.query_params)
    merged = {**{k.lower(): v for k, v in qp.items()}, **{k.lower(): v for k, v in headers.items()}}

    try:
        routing = resolve_routing(merged, path_sandbox_id=path_sandbox_id)
    except ValueError as exc:
        await websocket.close(code=1008, reason=str(exc))
        return

    await websocket.accept()

    try:
        await proxy_websocket(
            client_ws=websocket,
            sandbox_id=routing["sandbox_id"],
            path=path,
            namespace=routing["namespace"],
            port=routing["port"],
        )
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close(code=1011, reason="upstream connection failed")
        except RuntimeError:
            pass


# ── Path-based routes (browser-friendly, registered first) ───────────────────


@router.websocket("/{sandbox_id}/ws/{path:path}")
async def ws_proxy_by_path(websocket: WebSocket, sandbox_id: str, path: str) -> None:
    await _do_ws_proxy(websocket, path, path_sandbox_id=sandbox_id)


@router.api_route(
    "/{sandbox_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def http_proxy_by_path(request: Request, sandbox_id: str, path: str) -> StreamingResponse:
    return await _do_http_proxy(request, path, path_sandbox_id=sandbox_id)
