from treadstone.main import app
from treadstone.openapi_spec import build_full_openapi_spec


def test_browser_only_oauth_routes_are_hidden_from_openapi():
    app.openapi_schema = None
    spec = app.openapi()

    assert "/v1/auth/google/authorize" not in spec["paths"]
    assert "/v1/auth/google/callback" not in spec["paths"]
    assert "/v1/auth/github/authorize" not in spec["paths"]
    assert "/v1/auth/github/callback" not in spec["paths"]


def test_admin_paths_are_hidden_from_public_openapi():
    app.openapi_schema = None
    spec = app.openapi()

    assert "/v1/admin/stats" not in spec["paths"]
    assert "/v1/admin/tier-templates" not in spec["paths"]


def test_audit_paths_are_hidden_from_public_openapi():
    app.openapi_schema = None
    spec = app.openapi()

    assert "/v1/audit/events" not in spec["paths"]
    assert "/v1/audit/filter-options" not in spec["paths"]


def test_full_openapi_spec_includes_admin_for_export_tooling():
    app.openapi_schema = None
    full = build_full_openapi_spec(app)

    assert "/v1/admin/stats" in full["paths"]
    assert "/v1/audit/events" in full["paths"]
