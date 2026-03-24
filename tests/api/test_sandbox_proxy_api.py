"""API tests for the sandbox proxy router at /v1/sandboxes/{id}/proxy/."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User
from treadstone.services.sandbox_token import create_sandbox_token

_test_session_factory = None


@pytest.fixture
async def db_session():
    global _test_session_factory
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with _test_session_factory() as session:
            yield session

    async def override_get_user_db():
        async with _test_session_factory() as session:
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

    async def override_get_user_manager():
        async with _test_session_factory() as session:
            db = SQLAlchemyUserDatabase(session, User, OAuthAccount)
            yield UserManager(db)

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_user_db] = override_get_user_db
    app.dependency_overrides[get_user_manager] = override_get_user_manager
    yield
    app.dependency_overrides.clear()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def auth_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "proxy@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "proxy@test.com", "password": "Pass123!"})
        yield client


def _mock_upstream(body: bytes = b"", status: int = 200, headers: dict | None = None):
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = status
    mock_resp.headers = httpx.Headers(headers or {})

    async def fake_aiter():
        yield body

    mock_resp.aiter_bytes = fake_aiter

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.build_request.side_effect = lambda method, url, headers, content: httpx.Request(method, url)
    mock_client.send.return_value = mock_resp
    return mock_client


async def test_proxy_without_auth_returns_401(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/sandboxes/sb-123/proxy/healthz")
    assert resp.status_code == 401


async def test_proxy_nonexistent_sandbox_returns_404(auth_client):
    user_resp = await auth_client.get("/v1/auth/user")
    token, _ = create_sandbox_token("sb-nonexistent1234", user_resp.json()["id"], expires_in=3600)
    resp = await auth_client.get(
        "/v1/sandboxes/sb-nonexistent1234/proxy/healthz",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "sandbox_not_found"


async def test_proxy_stopped_sandbox_returns_409(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-stopped-sb"},
    )
    sandbox_id = create_resp.json()["id"]

    # Manually set status to stopped via DB
    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "stopped"
        session.add(sb)
        await session.commit()

    token_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    resp = await auth_client.get(
        f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "sandbox_not_ready"


async def test_proxy_success_for_ready_sandbox(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-ready-sb"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    mock_client = _mock_upstream(
        body=b'{"ok": true}',
        headers={"content-type": "application/json"},
    )
    token_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
        resp = await auth_client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


async def test_proxy_cookie_auth_returns_401_auth_invalid(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-cookie-sb"},
    )
    sandbox_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/proxy/healthz")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_invalid"


async def test_proxy_api_key_auth_returns_401_auth_invalid(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-api-key-sb"},
    )
    sandbox_id = create_resp.json()["id"]
    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-key"})
    api_key = key_resp.json()["key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_invalid"


async def test_proxy_scope_mismatch_returns_403(auth_client):
    first_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-scope-one"},
    )
    second_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-scope-two"},
    )
    first_id = first_resp.json()["id"]
    second_id = second_resp.json()["id"]

    token_resp = await auth_client.post(f"/v1/sandboxes/{first_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{second_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"
