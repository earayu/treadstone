from treadstone.openapi_spec import _SANDBOX_SCHEMA_RENAMES, filter_public_openapi, merge_sandbox_paths


def test_filter_public_openapi_removes_admin_paths() -> None:
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "0"},
        "paths": {
            "/v1/health": {"get": {}},
            "/v1/admin/stats": {"get": {}},
            "/v1/admin/users/{user_id}/plan": {"patch": {}},
        },
    }
    out = filter_public_openapi(spec)

    assert "/v1/health" in out["paths"]
    assert "/v1/admin/stats" not in out["paths"]
    assert "/v1/admin/users/{user_id}/plan" not in out["paths"]
    assert "/v1/admin/stats" in spec["paths"]


def test_filter_public_openapi_removes_audit_paths() -> None:
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "0"},
        "paths": {
            "/v1/usage": {"get": {}},
            "/v1/audit/events": {"get": {}},
            "/v1/audit/filter-options": {"get": {}},
        },
    }
    out = filter_public_openapi(spec)

    assert "/v1/usage" in out["paths"]
    assert "/v1/audit/events" not in out["paths"]
    assert "/v1/audit/filter-options" not in out["paths"]


# ---------------------------------------------------------------------------
# merge_sandbox_paths tests
# ---------------------------------------------------------------------------

_PROXY_PREFIX = "/v1/sandboxes/{sandbox_id}/proxy"


def _base_spec() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "t", "version": "0"},
        "paths": {"/v1/sandboxes": {"get": {}}},
        "components": {
            "schemas": {
                # Treadstone's own SandboxResponse: the entity DTO.
                "SandboxResponse": {
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "status": {"type": "string"},
                    }
                }
            }
        },
    }


def test_merge_sandbox_paths_adds_proxy_prefix() -> None:
    out = merge_sandbox_paths(_base_spec())
    proxy_paths = [p for p in out["paths"] if p.startswith(_PROXY_PREFIX)]
    assert len(proxy_paths) > 0, "No proxy paths were merged"
    for path in proxy_paths:
        assert path.startswith(_PROXY_PREFIX), f"Path missing proxy prefix: {path}"


def test_merge_sandbox_paths_injects_sandbox_id_param() -> None:
    out = merge_sandbox_paths(_base_spec())
    proxy_paths = [p for p in out["paths"] if p.startswith(_PROXY_PREFIX)]
    for path in proxy_paths:
        for method, operation in out["paths"][path].items():
            if not isinstance(operation, dict):
                continue
            param_names = [p["name"] for p in operation.get("parameters", [])]
            assert "sandbox_id" in param_names, f"sandbox_id param missing from {method.upper()} {path}"
            # sandbox_id must be the first parameter.
            assert param_names[0] == "sandbox_id", (
                f"sandbox_id must be first param in {method.upper()} {path}, got {param_names}"
            )


def test_merge_sandbox_paths_renames_conflicting_schemas() -> None:
    out = merge_sandbox_paths(_base_spec())
    schemas = out["components"]["schemas"]
    for original_name in _SANDBOX_SCHEMA_RENAMES:
        # The original name must not survive in the merged spec's schema keys
        # (it has either been renamed or was never in the sandbox spec).
        # What matters is that sandbox versions don't overwrite Treadstone versions.
        renamed = _SANDBOX_SCHEMA_RENAMES[original_name]
        if original_name in schemas:
            # If the key still exists, it must be Treadstone's version, not sandbox's.
            # We verify this for SandboxResponse specifically: Treadstone's DTO has "id".
            if original_name == "SandboxResponse":
                assert "id" in schemas[original_name].get("properties", {}), (
                    "Treadstone's SandboxResponse was overwritten by the sandbox spec version"
                )
        if renamed in schemas:
            assert renamed != original_name, f"Rename did not produce a different key: {renamed}"


def test_merge_sandbox_paths_does_not_include_terminal_route() -> None:
    out = merge_sandbox_paths(_base_spec())
    terminal_path = f"{_PROXY_PREFIX}/terminal"
    assert terminal_path not in out["paths"], "/terminal HTML route must not appear in merged spec"


def test_merge_sandbox_paths_retags_operations() -> None:
    out = merge_sandbox_paths(_base_spec())
    proxy_paths = [p for p in out["paths"] if p.startswith(_PROXY_PREFIX)]
    for path in proxy_paths:
        for method, operation in out["paths"][path].items():
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags", [])
            for tag in tags:
                assert tag.startswith("Sandbox: "), (
                    f"Tag {tag!r} in {method.upper()} {path} must start with 'Sandbox: '"
                )


def test_merge_sandbox_paths_preserves_treadstone_paths() -> None:
    out = merge_sandbox_paths(_base_spec())
    assert "/v1/sandboxes" in out["paths"], "Treadstone's own paths must be preserved"


def test_merge_sandbox_paths_is_idempotent_on_input() -> None:
    base = _base_spec()
    merge_sandbox_paths(base)
    # Original spec must not be mutated.
    assert list(base["paths"].keys()) == ["/v1/sandboxes"]
