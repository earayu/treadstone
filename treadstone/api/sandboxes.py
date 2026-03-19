"""Sandbox CRUD API router — control plane endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_user
from treadstone.core.database import get_session
from treadstone.models.user import User
from treadstone.services.sandbox_service import SandboxService

router = APIRouter(prefix="/v1/sandboxes", tags=["sandboxes"])


class CreateSandboxRequest(BaseModel):
    template: str
    name: str | None = None
    runtime_type: str = "aio"
    image: str = "ghcr.io/earayu/sandbox-runtime:latest"
    labels: dict = Field(default_factory=dict)
    auto_stop_interval: int = 15
    auto_delete_interval: int = -1


class SandboxResponse(BaseModel):
    id: str
    name: str
    template: str
    runtime_type: str
    status: str
    labels: dict
    auto_stop_interval: int
    auto_delete_interval: int
    created_at: str

    model_config = {"from_attributes": True}


class SandboxDetailResponse(SandboxResponse):
    image: str
    status_message: str | None = None
    endpoints: dict
    proxy_url: str
    started_at: str | None = None
    stopped_at: str | None = None


class SandboxListResponse(BaseModel):
    items: list[SandboxResponse]
    total: int


def _to_response(sb) -> dict:
    return {
        "id": sb.id,
        "name": sb.name,
        "template": sb.template,
        "runtime_type": sb.runtime_type,
        "status": sb.status,
        "labels": sb.labels or {},
        "auto_stop_interval": sb.auto_stop_interval,
        "auto_delete_interval": sb.auto_delete_interval,
        "created_at": str(sb.gmt_created) if sb.gmt_created else None,
    }


def _to_detail(sb) -> dict:
    data = _to_response(sb)
    data.update(
        {
            "image": sb.image,
            "status_message": sb.status_message,
            "endpoints": sb.endpoints or {},
            "proxy_url": f"/v1/sandboxes/{sb.id}/proxy",
            "started_at": str(sb.gmt_started) if sb.gmt_started else None,
            "stopped_at": str(sb.gmt_stopped) if sb.gmt_stopped else None,
        }
    )
    return data


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_sandbox(
    body: CreateSandboxRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.create(
        owner_id=user.id,
        template=body.template,
        image=body.image,
        name=body.name,
        runtime_type=body.runtime_type,
        labels=body.labels,
        auto_stop_interval=body.auto_stop_interval,
        auto_delete_interval=body.auto_delete_interval,
    )
    return _to_response(sandbox)


@router.get("")
async def list_sandboxes(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    label: list[str] = Query(default=[]),
):
    labels_dict: dict[str, str] = {}
    for lbl in label:
        if ":" in lbl:
            k, v = lbl.split(":", 1)
            labels_dict[k] = v

    service = SandboxService(session=session)
    sandboxes = await service.list_by_owner(owner_id=user.id, labels=labels_dict or None)
    return {"items": [_to_response(sb) for sb in sandboxes], "total": len(sandboxes)}


@router.get("/{sandbox_id}")
async def get_sandbox(
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    sandbox = await service.get(sandbox_id=sandbox_id, owner_id=user.id)
    if sandbox is None:
        raise HTTPException(status_code=404, detail=f"Sandbox {sandbox_id} not found")
    return _to_detail(sandbox)


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    try:
        await service.delete(sandbox_id=sandbox_id, owner_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"Sandbox {sandbox_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{sandbox_id}/start")
async def start_sandbox(
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    try:
        sandbox = await service.start(sandbox_id=sandbox_id, owner_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"Sandbox {sandbox_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_detail(sandbox)


@router.post("/{sandbox_id}/stop")
async def stop_sandbox(
    sandbox_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session)
    try:
        sandbox = await service.stop(sandbox_id=sandbox_id, owner_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail=f"Sandbox {sandbox_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _to_detail(sandbox)
