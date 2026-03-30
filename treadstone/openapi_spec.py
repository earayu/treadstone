"""Helpers for building OpenAPI documents and producing a public control-plane schema."""

from __future__ import annotations

import copy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

# Path prefixes omitted from public OpenAPI, runtime `/openapi.json`, and Python SDK.
HIDDEN_FROM_PUBLIC_PATH_PREFIXES: tuple[str, ...] = ("/v1/admin", "/v1/audit")


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
