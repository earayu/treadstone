"""Sandbox Templates API — read-only, served from K8s SandboxTemplate CRs."""

from fastapi import APIRouter, Depends

from treadstone.api.deps import get_current_user
from treadstone.api.schemas import SandboxTemplateListResponse
from treadstone.config import settings
from treadstone.models.user import User
from treadstone.services.k8s_client import get_k8s_client

router = APIRouter(prefix="/v1/sandbox-templates", tags=["sandbox-templates"])


@router.get("", response_model=SandboxTemplateListResponse)
async def list_templates(user: User = Depends(get_current_user)):
    k8s = get_k8s_client()
    templates = await k8s.list_sandbox_templates(namespace=settings.sandbox_namespace)
    return {"items": templates}
