"""Sandbox Templates API — read-only, served from K8s SandboxTemplate CRs."""

from fastapi import APIRouter

from treadstone.api.schemas import SandboxTemplateListResponse
from treadstone.config import settings
from treadstone.infra.services.k8s_client import get_k8s_client
from treadstone.sandbox.services.sandbox_templates import load_sandbox_template_catalog

router = APIRouter(prefix="/v1/sandbox-templates", tags=["sandbox-templates"])


@router.get("", response_model=SandboxTemplateListResponse)
async def list_sandbox_templates():
    k8s = get_k8s_client()
    templates = await load_sandbox_template_catalog(k8s, settings.sandbox_namespace)
    return {"items": templates}
