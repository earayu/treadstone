import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app


@pytest.mark.asyncio
async def test_config_returns_auth_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth" in data
    assert "type" in data["auth"]


@pytest.mark.asyncio
async def test_config_includes_login_methods():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/config")
    data = resp.json()
    assert "login_methods" in data["auth"]
    assert "email" in data["auth"]["login_methods"]
