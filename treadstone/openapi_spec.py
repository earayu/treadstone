"""Helpers for building OpenAPI documents and producing a public control-plane schema."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# Path prefixes omitted from public OpenAPI, runtime `/openapi.json`, and Python SDK.
HIDDEN_FROM_PUBLIC_PATH_PREFIXES: tuple[str, ...] = ("/v1/admin", "/v1/audit")

# Sandbox OpenAPI base file bundled with the repo (relative to this file's package root).
_SANDBOX_SPEC_PATH = Path(__file__).parent.parent / "scripts" / "sandbox_openapi_base.json"

# Sandbox schemas that collide with Treadstone's own schema names — rename them before merging.
_SANDBOX_SCHEMA_RENAMES: dict[str, str] = {
    "Response": "SandboxApiResponse",
    "ValidationError": "SandboxValidationError",
    "HTTPValidationError": "SandboxHTTPValidationError",
}

# Path parameter injected into every proxied sandbox operation.
_SANDBOX_ID_PARAM: dict[str, Any] = {
    "name": "sandbox_id",
    "in": "path",
    "required": True,
    "schema": {"type": "string", "title": "Sandbox Id"},
    "description": "ID of the target sandbox.",
}


def _path_hidden_from_public(path: str) -> bool:
    for prefix in HIDDEN_FROM_PUBLIC_PATH_PREFIXES:
        if path == prefix or path.startswith(f"{prefix}/"):
            return True
    return False


def build_full_openapi_spec(app: FastAPI) -> dict[str, Any]:
    """Full OpenAPI schema including routes marked for internal tooling (e.g. export, web types)."""
    return get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        summary=app.summary,
        description=app.description,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        routes=app.routes,
        webhooks=app.webhooks.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        separate_input_output_schemas=app.separate_input_output_schemas,
        external_docs=app.openapi_external_docs,
    )


def filter_public_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *spec* without privileged paths (admin, audit) for public OpenAPI and Python SDK."""
    out = copy.deepcopy(spec)
    paths = out.get("paths") or {}
    keys_to_drop = [p for p in paths if _path_hidden_from_public(p)]
    for k in keys_to_drop:
        paths.pop(k, None)
    out["paths"] = paths
    return out


def merge_sandbox_paths(spec: dict[str, Any], sandbox_spec_path: Path = _SANDBOX_SPEC_PATH) -> dict[str, Any]:
    """Merge sandbox runtime API paths into *spec* for display in Swagger UI docs.

    Each sandbox path is prefixed with ``/v1/sandboxes/{sandbox_id}/proxy`` so that
    callers can invoke sandbox operations through the Treadstone HTTP proxy.  The
    ``sandbox_id`` path parameter is injected into every operation automatically.

    Conflicting schema names (``Response``, ``ValidationError``, ``HTTPValidationError``)
    are renamed with a ``Sandbox`` prefix before merging so they do not overwrite
    Treadstone's own schemas.

    This function is intentionally *not* called from ``export_openapi.py`` so the
    Python SDK (generated from ``openapi-public.json``) remains unchanged.
    """
    if not sandbox_spec_path.exists():
        return spec

    with sandbox_spec_path.open() as fh:
        raw = fh.read()

    # Rename conflicting schema $ref strings before parsing so every internal
    # reference inside the sandbox spec is updated in one pass.
    for old, new in _SANDBOX_SCHEMA_RENAMES.items():
        raw = raw.replace(
            f'"#/components/schemas/{old}"',
            f'"#/components/schemas/{new}"',
        )
    sandbox_spec: dict[str, Any] = json.loads(raw)

    # Rename the schema *keys* in components/schemas to match the updated $refs.
    sandbox_schemas: dict[str, Any] = (sandbox_spec.get("components") or {}).get("schemas") or {}
    renamed_schemas: dict[str, Any] = {}
    for key, value in sandbox_schemas.items():
        renamed_schemas[_SANDBOX_SCHEMA_RENAMES.get(key, key)] = value

    out = copy.deepcopy(spec)

    # Merge renamed schemas (sandbox names are unique enough to not collide further).
    out.setdefault("components", {}).setdefault("schemas", {}).update(renamed_schemas)

    # Re-prefix each sandbox path and inject the sandbox_id parameter.
    proxy_prefix = "/v1/sandboxes/{sandbox_id}/proxy"
    for path, path_item in (sandbox_spec.get("paths") or {}).items():
        new_path = f"{proxy_prefix}{path}"
        new_item: dict[str, Any] = {}
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                new_item[method] = operation
                continue

            op = copy.deepcopy(operation)

            # Re-group under a "Sandbox: <original_tag>" tag so the Swagger UI
            # shows sandbox operations in clearly labelled sections.
            original_tags = op.get("tags") or ["sandbox-runtime"]
            op["tags"] = [f"Sandbox: {t}" for t in original_tags]

            # Prefix operationId to avoid any collision with Treadstone operations.
            if "operationId" in op:
                op["operationId"] = f"sandbox_runtime_{op['operationId']}"

            # Inject sandbox_id as the first path parameter.
            existing_params = op.get("parameters") or []
            op["parameters"] = [_SANDBOX_ID_PARAM, *existing_params]

            new_item[method] = op

        out["paths"][new_path] = new_item

    return out
