from treadstone.openapi_spec import filter_public_openapi


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
