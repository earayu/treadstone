import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app


@pytest.mark.asyncio
async def test_protected_route_no_auth_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_invalid_bearer_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/me", headers={"Authorization": "Bearer invalid-token"})
    assert resp.status_code == 401
