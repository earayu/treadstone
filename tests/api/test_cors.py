"""CORS middleware tests — verify the Web UI frontend can call the API cross-origin."""


async def test_cors_preflight_returns_allow_headers(client):
    response = await client.options(
        "/health",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


async def test_cors_simple_request_includes_headers(client):
    response = await client.get("/health", headers={"origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_cors_disallowed_origin_no_header(client):
    response = await client.get("/health", headers={"origin": "http://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
