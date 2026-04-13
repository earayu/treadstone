"""Sandbox template catalog read path helpers."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from treadstone.api.schemas import SandboxTemplateResponse
from treadstone.core.errors import SandboxTemplateCatalogUnavailableError
from treadstone.infra.services.k8s_client import K8sClientProtocol

logger = logging.getLogger(__name__)


async def load_sandbox_template_catalog(k8s: K8sClientProtocol, namespace: str) -> list[dict[str, Any]]:
    """Load, validate, and sort sandbox templates for API responses."""
    try:
        raw_templates = await k8s.list_sandbox_templates(namespace=namespace)
    except Exception as exc:
        logger.exception("Failed to load sandbox template catalog from namespace %s", namespace)
        if isinstance(exc, (TypeError, ValueError, AttributeError)):
            raise
        raise SandboxTemplateCatalogUnavailableError() from exc

    templates: list[dict[str, Any]] = []
    for raw_template in raw_templates:
        try:
            template = SandboxTemplateResponse.model_validate(raw_template)
        except PydanticValidationError:
            template_name = raw_template.get("name", "<unknown>")
            logger.warning("Skipping malformed sandbox template %s from namespace %s", template_name, namespace)
            continue
        templates.append(template.model_dump(mode="json"))

    templates.sort(key=lambda item: item["name"])
    return templates
