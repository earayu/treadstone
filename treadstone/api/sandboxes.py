"""Sandbox CRUD API router — control plane endpoints."""

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_user
from treadstone.api.schemas import (
    CreateSandboxRequest,
    CreateSandboxTokenRequest,
    SandboxDetailResponse,
    SandboxListResponse,
    SandboxResponse,
    SandboxTokenResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import ForbiddenError, SandboxNotFoundError
from treadstone.models.user import User
from treadstone.services.sandbox_service import SandboxService
from treadstone.services.sandbox_token import create_sandbox_token

router = APIRouter(prefix="/v1/sandboxes", tags=["sandboxes"])


def _build_urls(sb, base_url: str) -> dict:
    base = str(base_url).rstrip("/")
    proxy = f"{base}/v1/sandboxes/{sb.id}/proxy"
    web = None
    if settings.sandbox_domain:
        scheme = "https" if base.startswith("https") else "http"
        port_suffix = ""
        if "localhost" in base:
            try:
                port_suffix = f":{base.rsplit(':', 1)[1].rstrip('/')}"
            except (IndexError, ValueError):
                pass
        web = f"{scheme}://{sb.name}.{settings.sandbox_domain}{port_suffix}"
    return {"proxy": proxy, "web": web}


def _to_response(sb, base_url: str) -> dict:
    return {
        "id": sb.id,
        "name": sb.name,
        "template": sb.template,
        "status": sb.status,
        "labels": sb.labels or {},
        "auto_stop_interval": sb.auto_stop_interval,
        "auto_delete_interval": sb.auto_delete_interval,
        "urls": _build_urls(sb, base_url),
        "created_at": sb.gmt_created,
    }


def _to_detail(sb, base_url: str) -> dict:
    data = _to_response(sb, base_url)
    data.update(
        {
            "image": sb.image,
            "status_message": sb.status_message,
            "persist": sb.persist,
            "storage_size": sb.storage_size,
            "started_at": sb.gmt_started,
            "stopped_at": sb.gmt_stopped,
        }
    )
    return data


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=SandboxResponse)
async def create_sandbox(
    request: Request,
    body: CreateSandboxRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.create(
        owner_id=user.id,
        template=body.template,
        name=body.name,
        labels=body.labels,
        auto_stop_interval=body.auto_stop_interval,
        auto_delete_interval=body.auto_delete_interval,
        persist=body.persist,
        storage_size=body.storage_size,
    )
    return _to_response(sandbox, str(request.base_url))


@router.get("", response_model=SandboxListResponse)
async def list_sandboxes(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    label: list[str] = Query(default=[]),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of items to return."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
):
    labels_dict: dict[str, str] = {}
    for lbl in label:
        if ":" in lbl:
            k, v = lbl.split(":", 1)
            labels_dict[k] = v

    service = SandboxService(session=session)
    sandboxes = await service.list_by_owner(owner_id=user.id, labels=labels_dict or None)
    total = len(sandboxes)
    page = sandboxes[offset : offset + limit]
    base_url = str(request.base_url)
    return {"items": [_to_response(sb, base_url) for sb in page], "total": total}


@router.get("/{sandbox_id}", response_model=SandboxDetailResponse)
async def get_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    payload = getattr(request.state, "sandbox_token_payload", None)
    if payload and payload["sandbox_id"] != sandbox_id:
        raise ForbiddenError("Sandbox Token scope mismatch: token is for a different sandbox")

    service = SandboxService(session=session)
    sandbox = await service.get(sandbox_id=sandbox_id, owner_id=user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)
    return _to_detail(sandbox, str(request.base_url))


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    await service.delete(sandbox_id=sandbox_id, owner_id=user.id)


@router.post("/{sandbox_id}/start", response_model=SandboxDetailResponse)
async def start_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.start(sandbox_id=sandbox_id, owner_id=user.id)
    return _to_detail(sandbox, str(request.base_url))


@router.post("/{sandbox_id}/stop", response_model=SandboxDetailResponse)
async def stop_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.stop(sandbox_id=sandbox_id, owner_id=user.id)
    return _to_detail(sandbox, str(request.base_url))


@router.post("/{sandbox_id}/token", status_code=status.HTTP_201_CREATED, response_model=SandboxTokenResponse)
async def create_sandbox_token_endpoint(
    sandbox_id: str,
    body: CreateSandboxTokenRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.get(sandbox_id=sandbox_id, owner_id=user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)

    token, expires_at = create_sandbox_token(
        sandbox_id=sandbox.id,
        user_id=user.id,
        expires_in=body.expires_in,
    )
    return {"token": token, "sandbox_id": sandbox.id, "expires_at": expires_at}
