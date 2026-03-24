"""API tests for Sandbox Token endpoints."""

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
        await client.post("/v1/auth/register", json={"email": "token@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "token@test.com", "password": "Pass123!"})
        yield client


async def test_create_sandbox_token(auth_client):
    create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "token-sb"})
    sandbox_id = create_resp.json()["id"]
    resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    assert resp.status_code == 201
    data = resp.json()
    assert "token" in data
    assert data["sandbox_id"] == sandbox_id
    assert "expires_at" in data


async def test_create_sandbox_token_invalid_expiration_returns_422(auth_client):
    create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "token-exp-sb"})
    sandbox_id = create_resp.json()["id"]
    resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 0})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_sandbox_token_cannot_access_control_plane(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "token-detail-sb"}
    )
    sandbox_id = create_resp.json()["id"]
    token_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{sandbox_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_invalid"


async def test_sandbox_token_cannot_mint_new_tokens(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "token-mint-sb"}
    )
    sandbox_id = create_resp.json()["id"]
    token_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/v1/sandboxes/{sandbox_id}/token",
            json={"expires_in": 3600},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_invalid"


async def test_sandbox_token_can_proxy(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "token-proxy-sb"}
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    token_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/token", json={"expires_in": 3600})
    token = token_resp.json()["token"]

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({"content-type": "application/json"})

    async def fake_aiter():
        yield b'{"ok":true}'

    mock_resp.aiter_bytes = fake_aiter
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False
    mock_client.build_request.side_effect = lambda method, url, headers, content: httpx.Request(method, url)
    mock_client.send.return_value = mock_resp

    with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
                headers={"Authorization": f"Bearer {token}"},
            )
    assert resp.status_code == 200


async def test_sandbox_token_nonexistent_sandbox_returns_404(auth_client):
    resp = await auth_client.post("/v1/sandboxes/sb-nonexistent1234/token", json={"expires_in": 3600})
    assert resp.status_code == 404


async def test_sandbox_token_for_nonexistent_target_returns_404(auth_client):
    token, _ = create_sandbox_token("sb-nonexistent1234", "user" + "1" * 16, expires_in=3600)

    async with _test_session_factory() as session:
        user = User(
            id="user" + "1" * 16,
            email="nonexistent-target@test.com",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
            role="ro",
        )
        session.add(user)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/v1/sandboxes/sb-nonexistent1234/proxy/healthz",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "sandbox_not_found"
