"""API tests for Sandbox CRUD endpoints."""

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditEvent
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import OAuthAccount, User
from treadstone.services.k8s_client import FakeK8sClient, set_k8s_client

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


@pytest.fixture
async def second_auth_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "other@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "other@test.com", "password": "Pass123!"})
        yield client


def _enable_subdomain(monkeypatch, domain: str = "sandbox.localhost", app_base_url: str = "http://test"):
    monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", domain)
    monkeypatch.setenv("TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX", "sandbox-")
    monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "default")
    monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "8080")
    monkeypatch.setenv("TREADSTONE_APP_BASE_URL", app_base_url)
    monkeypatch.setenv("TREADSTONE_JWT_SECRET", "test-jwt-secret-should-be-32-bytes!")
    from treadstone.config import Settings

    s = Settings()
    monkeypatch.setattr("treadstone.services.browser_login.settings", s)
    monkeypatch.setattr("treadstone.api.sandboxes.settings", s)
    monkeypatch.setattr("treadstone.core.users.settings", s)
    monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.settings", s)
    monkeypatch.setattr("treadstone.services.sandbox_service.settings", s)
    monkeypatch.setattr("treadstone.services.browser_auth.settings", s)
    monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)


class TestCreateSandbox:
    async def test_create_returns_202(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "my-sb"},
            headers={"X-Request-Id": "req-sandbox-create"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["name"] == "my-sb"
        assert data["status"] == "creating"
        assert data["template"] == "aio-sandbox-tiny"
        assert "id" in data
        assert resp.headers["X-Request-Id"] == "req-sandbox-create"

        async with _test_session_factory() as session:
            events = (
                (await session.execute(select(AuditEvent).where(AuditEvent.action == "sandbox.create"))).scalars().all()
            )

        assert len(events) == 1
        assert events[0].request_id == "req-sandbox-create"
        assert events[0].target_id == data["id"]

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

    async def test_create_with_persist_uses_default_storage_size(self, auth_client):
        create_resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "persist-default", "persist": True},
        )
        assert create_resp.status_code == 202

        sandbox_id = create_resp.json()["id"]
        get_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["storage_size"] == "5Gi"

    async def test_create_with_missing_storage_class_returns_503(self, auth_client):
        k8s = FakeK8sClient()
        k8s.remove_storage_class("treadstone-workspace")
        set_k8s_client(k8s)

        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "persist-no-sc", "persist": True},
        )

        assert resp.status_code == 503
        data = resp.json()
        assert data["error"]["code"] == "storage_backend_not_ready"

    async def test_create_with_subdomain_returns_shareable_web_entry_url(self, auth_client, monkeypatch):
        _enable_subdomain(monkeypatch)

        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "handoff-sb"},
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["urls"]["web"].startswith(
            f"http://sandbox-{data['id']}.sandbox.localhost/_treadstone/open?token=swl"
        )

    async def test_create_same_name_for_different_users_succeeds(self, auth_client, second_auth_client):
        first = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "shared-name"})
        second = await second_auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "shared-name"},
        )

        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] != second.json()["id"]

    async def test_create_same_name_for_same_user_returns_409(self, auth_client):
        first = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "taken-name"})
        second = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "taken-name"})

        assert first.status_code == 202
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "sandbox_name_conflict"

    @pytest.mark.parametrize(
        "name",
        [
            "BadName",
            "-leading-dash",
            "trailing-dash-",
            "has_underscore",
            "has.dot",
            "a" * 56,
        ],
    )
    async def test_create_with_invalid_name_returns_422(self, auth_client, name):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": name},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "validation_error"
        assert "Sandbox name must be 1-55 characters" in data["error"]["message"]

    async def test_create_accepts_name_at_max_length(self, auth_client):
        name = "a" * 55
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": name},
        )
        assert resp.status_code == 202
        assert resp.json()["name"] == name

    async def test_create_with_storage_size_without_persist_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-storage", "storage_size": "5Gi"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_create_with_invalid_storage_size_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-storage-size", "persist": True, "storage_size": "5GB"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_create_with_unsupported_storage_tier_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-storage-tier", "persist": True, "storage_size": "7Gi"},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"]["code"] == "validation_error"
        assert "5Gi" in data["error"]["message"]

    async def test_create_with_invalid_auto_stop_interval_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-stop", "auto_stop_interval": 0},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_create_with_invalid_auto_delete_interval_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-delete", "auto_delete_interval": 0},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


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

    async def test_list_with_invalid_label_filter_returns_422(self, auth_client):
        resp = await auth_client.get("/v1/sandboxes?label=invalid")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


class TestGetSandbox:
    async def test_get_existing_sandbox(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "get-sb"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == sandbox_id

    async def test_get_returns_current_shareable_web_url_when_web_link_is_enabled(self, auth_client, monkeypatch):
        _enable_subdomain(monkeypatch)
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "get-web"})
        sandbox_id = create_resp.json()["id"]

        resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}")

        assert resp.status_code == 200
        assert resp.json()["urls"]["web"].startswith(
            f"http://sandbox-{sandbox_id}.sandbox.localhost/_treadstone/open?token=swl"
        )

    async def test_web_enable_returns_same_current_shareable_url_created_with_sandbox(self, auth_client, monkeypatch):
        _enable_subdomain(monkeypatch)
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "get-web"})
        sandbox_id = create_resp.json()["id"]

        enable_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")

        assert enable_resp.status_code == 200
        assert enable_resp.json()["open_link"] == create_resp.json()["urls"]["web"]

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

    async def test_delete_revokes_active_web_link(self, auth_client, monkeypatch):
        _enable_subdomain(monkeypatch)
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "del-web"})
        sandbox_id = create_resp.json()["id"]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}")
        status_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")

        assert delete_resp.status_code == 204
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is False

    async def test_delete_keeps_row_until_sync_removes_it(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "del-row"})
        sandbox_id = create_resp.json()["id"]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}")

        assert delete_resp.status_code == 204
        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            assert sandbox is not None
            assert sandbox.status == "deleting"


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
