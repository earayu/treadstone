"""API tests for Sandbox CRUD endpoints."""

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.user import OAuthAccount, User

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
    """Register + login, return client with auth cookie."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "sandbox@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "sandbox@test.com", "password": "Pass123!"})
        yield client


class TestCreateSandbox:
    async def test_create_returns_202(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "my-sb"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["name"] == "my-sb"
        assert data["status"] == "creating"
        assert data["template"] == "aio-sandbox-tiny"
        assert "id" in data

    async def test_create_auto_generates_name(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny"},
        )
        assert resp.status_code == 202
        assert resp.json()["name"].startswith("sb-")

    async def test_create_without_auth_returns_401(self, db_session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny"})
        assert resp.status_code == 401

    async def test_create_with_invalid_template_returns_404(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "nonexistent-template", "name": "bad-tmpl-sb"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "template_not_found"

    async def test_create_with_persist_returns_202(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "persist-sb", "persist": True, "storage_size": "5Gi"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["name"] == "persist-sb"
        assert data["status"] == "creating"


class TestListSandboxes:
    async def test_list_returns_own_sandboxes(self, auth_client):
        await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "list-sb-1"})
        await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "list-sb-2"})
        resp = await auth_client.get("/v1/sandboxes")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2

    async def test_list_with_label_filter(self, auth_client):
        await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "labeled-sb", "labels": {"env": "dev"}},
        )
        await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "no-label-sb"},
        )
        resp = await auth_client.get("/v1/sandboxes?label=env:dev")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(item.get("labels", {}).get("env") == "dev" for item in items)


class TestGetSandbox:
    async def test_get_existing_sandbox(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "get-sb"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sandbox_id

    async def test_get_nonexistent_returns_404(self, auth_client):
        resp = await auth_client.get("/v1/sandboxes/sb-nonexistent1234")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "sandbox_not_found"


class TestDeleteSandbox:
    async def test_delete_from_creating_returns_204(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "del-sb"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_returns_404(self, auth_client):
        resp = await auth_client.delete("/v1/sandboxes/sb-nonexistent1234")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "sandbox_not_found"


class TestStartStopSandbox:
    async def test_start_from_creating_returns_409(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "start-sb"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/start")
        assert resp.status_code == 409

    async def test_stop_from_creating_returns_409(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "stop-sb"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/stop")
        assert resp.status_code == 409
