from treadstone.main import app


def test_browser_only_oauth_routes_are_hidden_from_openapi():
    app.openapi_schema = None
    spec = app.openapi()

    assert "/v1/auth/google/authorize" not in spec["paths"]
    assert "/v1/auth/google/callback" not in spec["paths"]
    assert "/v1/auth/github/authorize" not in spec["paths"]
    assert "/v1/auth/github/callback" not in spec["paths"]
