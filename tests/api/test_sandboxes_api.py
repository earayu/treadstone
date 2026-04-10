"""API tests for Sandbox CRUD endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.audit_event import AuditEvent
from treadstone.models.platform_limits import PLATFORM_LIMITS_SINGLETON_ID, PlatformLimits
from treadstone.models.sandbox import Sandbox, SandboxStatus, StorageBackendMode
from treadstone.models.user import OAuthAccount, User
from treadstone.services.k8s_client import FakeK8sClient, get_k8s_client, set_k8s_client

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


async def _set_platform_limits(**limits) -> None:
    async with _test_session_factory() as session:
        row = await session.get(PlatformLimits, PLATFORM_LIMITS_SINGLETON_ID)
        if row is None:
            row = PlatformLimits(id=PLATFORM_LIMITS_SINGLETON_ID)
        for field, value in limits.items():
            setattr(row, field, value)
        session.add(row)
        await session.commit()
        await app.state.platform_limits_runtime.refresh_from_session(session)


async def _refresh_platform_limits_runtime_cache() -> None:
    """Align the API process snapshot with the database (tests only)."""
    async with _test_session_factory() as session:
        await app.state.platform_limits_runtime.refresh_from_session(session)


@pytest.fixture
async def auth_client(db_session):
    """Register + login, return client with auth cookie."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "sandbox@test.com", "password": "Pass123!"})
        async with _test_session_factory() as session:
            user = (await session.execute(select(User).where(User.email == "sandbox@test.com"))).unique().scalar_one()
            user.is_verified = True
            session.add(user)
            await session.commit()
        await client.post("/v1/auth/login", json={"email": "sandbox@test.com", "password": "Pass123!"})
        yield client


@pytest.fixture
async def second_auth_client(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "other@test.com", "password": "Pass123!"})
        async with _test_session_factory() as session:
            user = (await session.execute(select(User).where(User.email == "other@test.com"))).unique().scalar_one()
            user.is_verified = True
            session.add(user)
            await session.commit()
        await client.post("/v1/auth/login", json={"email": "other@test.com", "password": "Pass123!"})
        yield client


def _enable_subdomain(monkeypatch, domain: str = "sandbox.localhost", app_base_url: str = "http://test"):
    monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", domain)
    monkeypatch.setenv("TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX", "sandbox-")
    monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "default")
    monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "8080")
    monkeypatch.setenv("TREADSTONE_APP_BASE_URL", app_base_url)
    monkeypatch.setenv("TREADSTONE_JWT_SECRET", "test-jwt-secret-should-be-32-bytes!")
    monkeypatch.setenv("TREADSTONE_METERING_ENFORCEMENT_ENABLED", "false")
    from treadstone.config import Settings

    s = Settings()
    monkeypatch.setattr("treadstone.services.browser_login.settings", s)
    monkeypatch.setattr("treadstone.api.sandboxes.settings", s)
    monkeypatch.setattr("treadstone.core.public_base_url.settings", s)
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

    async def test_create_respects_total_sandbox_cap(self, auth_client):
        await _set_platform_limits(max_total_sandboxes=1)

        first = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "cap-a"})
        assert first.status_code == 202
        await _refresh_platform_limits_runtime_cache()
        second = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "cap-b"})

        assert second.status_code == 503
        assert second.json()["error"]["code"] == "sandbox_cap_exceeded"

        async with _test_session_factory() as session:
            event = (
                (
                    await session.execute(
                        select(AuditEvent).where(AuditEvent.action == "sandbox.create").order_by(AuditEvent.created_at)
                    )
                )
                .scalars()
                .all()[-1]
            )

        assert event.result == "failure"
        assert event.error_code == "sandbox_cap_exceeded"

    async def test_create_persistent_sandbox_respects_global_storage_cap(self, auth_client):
        await _set_platform_limits(max_total_storage_gib=0)

        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "persist-capped", "persist": True, "storage_size": "5Gi"},
        )

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "global_storage_cap_exceeded"

    async def test_create_non_persistent_sandbox_ignores_global_storage_cap(self, auth_client):
        await _set_platform_limits(max_total_storage_gib=0)

        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "ephemeral-ok", "persist": False},
        )

        assert resp.status_code == 202

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

    async def test_create_ignores_spoofed_forwarded_host_when_public_app_base_url_configured(
        self, auth_client, monkeypatch
    ):
        _enable_subdomain(monkeypatch, domain="treadstone-ai.dev", app_base_url="https://app.treadstone-ai.dev")

        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "public-origin-sb"},
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "evil.example.com",
                "Host": "evil.example.com",
            },
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["urls"]["proxy"].startswith(f"https://app.treadstone-ai.dev/v1/sandboxes/{data['id']}/proxy")
        assert data["urls"]["mcp"].startswith(f"https://app.treadstone-ai.dev/v1/sandboxes/{data['id']}/proxy/mcp")
        assert data["urls"]["web"].startswith(f"https://sandbox-{data['id']}.treadstone-ai.dev/_treadstone/open?token=")
        assert "evil.example.com" not in data["urls"]["proxy"]
        assert "evil.example.com" not in data["urls"]["web"]

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

    async def test_create_with_unsupported_storage_tier_returns_400(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-storage-tier", "persist": True, "storage_size": "7Gi"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["code"] == "bad_request"
        assert "7Gi" in data["error"]["message"]
        assert "5Gi" in data["error"]["message"]

    async def test_create_with_invalid_auto_stop_interval_returns_422(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "bad-stop", "auto_stop_interval": -1},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"

    async def test_create_with_zero_auto_stop_interval_accepted(self, auth_client):
        resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "never-stop", "auto_stop_interval": 0},
        )
        assert resp.status_code < 400

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

    async def test_list_orders_ready_before_stopped(self, auth_client):
        r_stopped = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "order-stopped"},
        )
        r_ready = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "order-ready"},
        )
        id_stopped = r_stopped.json()["id"]
        id_ready = r_ready.json()["id"]
        async with _test_session_factory() as session:
            sb_s = (await session.execute(select(Sandbox).where(Sandbox.id == id_stopped))).scalar_one()
            sb_s.status = "stopped"
            sb_r = (await session.execute(select(Sandbox).where(Sandbox.id == id_ready))).scalar_one()
            sb_r.status = "ready"
            await session.commit()

        resp = await auth_client.get("/v1/sandboxes")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert ids.index(id_ready) < ids.index(id_stopped)

    async def test_list_same_status_orders_by_activity_then_name(self, auth_client):
        r_old = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "act-old"},
        )
        r_new = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "act-new"},
        )
        id_old = r_old.json()["id"]
        id_new = r_new.json()["id"]
        now = datetime.now(UTC)
        async with _test_session_factory() as session:
            sb_o = (await session.execute(select(Sandbox).where(Sandbox.id == id_old))).scalar_one()
            sb_o.status = "ready"
            sb_o.gmt_last_active = now - timedelta(hours=2)
            sb_n = (await session.execute(select(Sandbox).where(Sandbox.id == id_new))).scalar_one()
            sb_n.status = "ready"
            sb_n.gmt_last_active = now - timedelta(minutes=5)
            await session.commit()

        resp = await auth_client.get("/v1/sandboxes")
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert ids.index(id_new) < ids.index(id_old)

    async def test_list_order_stable_across_requests(self, auth_client):
        await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "stable-a"})
        await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "stable-b"})
        first = await auth_client.get("/v1/sandboxes")
        second = await auth_client.get("/v1/sandboxes")
        assert first.json()["items"] == second.json()["items"]


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


class TestPatchSandbox:
    async def test_patch_updates_name_and_labels(self, auth_client):
        create_resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "patch-orig"},
        )
        assert create_resp.status_code == 202
        sandbox_id = create_resp.json()["id"]

        resp = await auth_client.patch(
            f"/v1/sandboxes/{sandbox_id}",
            json={"name": "patch-new", "labels": {"env": "staging"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "patch-new"
        assert data["labels"] == {"env": "staging"}

        async with _test_session_factory() as session:
            events = (
                (await session.execute(select(AuditEvent).where(AuditEvent.action == "sandbox.update"))).scalars().all()
            )
        assert len(events) == 1
        assert events[0].target_id == sandbox_id

    async def test_patch_empty_body_returns_422(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "patch-e"})
        sandbox_id = create_resp.json()["id"]
        resp = await auth_client.patch(f"/v1/sandboxes/{sandbox_id}", json={})
        assert resp.status_code == 422


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
        assert status_resp.status_code in {200, 404}
        if status_resp.status_code == 200:
            assert status_resp.json()["enabled"] is False
        else:
            assert status_resp.json()["error"]["code"] == "sandbox_not_found"

    async def test_delete_keeps_row_until_sync_removes_it(self, auth_client):
        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "del-row"})
        sandbox_id = create_resp.json()["id"]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}")

        assert delete_resp.status_code == 204
        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            assert sandbox is not None
            assert sandbox.status == "deleting"

    async def test_delete_returns_409_when_bound_snapshot_cleanup_fails(self, auth_client):
        create_resp = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "del-snapshot-fail", "persist": True, "storage_size": "5Gi"},
        )
        sandbox_id = create_resp.json()["id"]

        k8s = get_k8s_client()
        assert isinstance(k8s, FakeK8sClient)

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            await k8s.create_volume_snapshot(
                name=f"{sandbox_id}-workspace-snapshot",
                namespace=sandbox.k8s_namespace,
                source_pvc_name=f"{sandbox.k8s_sandbox_name}-workspace",
                snapshot_class_name="treadstone-workspace-snapshot",
            )
            sandbox.status = SandboxStatus.READY
            sandbox.storage_backend_mode = StorageBackendMode.LIVE_DISK
            sandbox.snapshot_k8s_volume_snapshot_name = f"{sandbox_id}-workspace-snapshot"
            sandbox.snapshot_k8s_volume_snapshot_content_name = f"vsc-{sandbox_id}-workspace-snapshot"
            session.add(sandbox)
            await session.commit()

        async def _fail_delete_snapshot(name: str, namespace: str) -> bool:
            raise RuntimeError("delete failed")

        k8s.delete_volume_snapshot = _fail_delete_snapshot  # type: ignore[assignment]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}")

        assert delete_resp.status_code == 409
        assert delete_resp.json()["error"]["code"] == "conflict"

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            assert sandbox is not None
            assert sandbox.status == SandboxStatus.ERROR
            assert sandbox.status_message == "Failed to delete bound snapshot during sandbox delete"

    async def test_soft_deleted_sandbox_not_in_list(self, auth_client):
        """After soft-delete, the sandbox should not appear in the list API."""
        from treadstone.models.sandbox import SandboxStatus
        from treadstone.models.user import utc_now

        create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "ghost-sb"})
        sandbox_id = create_resp.json()["id"]

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            sandbox.status = SandboxStatus.DELETED
            sandbox.gmt_deleted = utc_now()
            session.add(sandbox)
            await session.commit()

        list_resp = await auth_client.get("/v1/sandboxes")
        assert list_resp.status_code == 200
        ids = [item["id"] for item in list_resp.json()["items"]]
        assert sandbox_id not in ids

    async def test_soft_deleted_sandbox_not_found_by_get(self, auth_client):
        """After soft-delete, GET by id should return 404."""
        from treadstone.models.sandbox import SandboxStatus
        from treadstone.models.user import utc_now

        create_resp = await auth_client.post(
            "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "ghost-get-sb"}
        )
        sandbox_id = create_resp.json()["id"]

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            sandbox.status = SandboxStatus.DELETED
            sandbox.gmt_deleted = utc_now()
            session.add(sandbox)
            await session.commit()

        get_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}")
        assert get_resp.status_code == 404

    @pytest.mark.skipif(
        True,
        reason="Partial unique index (postgresql_where) is not enforced in SQLite; "
        "this behaviour is covered by integration tests against Postgres.",
    )
    async def test_recreate_sandbox_with_same_name_after_soft_delete(self, auth_client):
        """Partial unique index allows re-creating a sandbox with the same name after deletion."""
        from treadstone.models.sandbox import SandboxStatus
        from treadstone.models.user import utc_now

        first_resp = await auth_client.post(
            "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "reuse-name"}
        )
        assert first_resp.status_code == 202
        first_id = first_resp.json()["id"]

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, first_id)
            sandbox.status = SandboxStatus.DELETED
            sandbox.gmt_deleted = utc_now()
            session.add(sandbox)
            await session.commit()

        second_resp = await auth_client.post(
            "/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": "reuse-name"}
        )
        assert second_resp.status_code == 202
        assert second_resp.json()["id"] != first_id
        assert second_resp.json()["name"] == "reuse-name"


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


class TestColdSnapshotRoutes:
    async def test_snapshot_route_sets_pending_operation(self, auth_client):
        create = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "cold-snap", "persist": True, "storage_size": "5Gi"},
        )
        sandbox_id = create.json()["id"]

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            sandbox.status = SandboxStatus.READY
            sandbox.storage_backend_mode = StorageBackendMode.LIVE_DISK
            session.add(sandbox)
            await session.commit()

        resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/snapshot")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "stopped"
        assert data["pending_operation"] == "snapshotting"
        assert data["storage"]["mode"] == "live_disk"

    async def test_start_route_on_cold_sandbox_queues_restore_and_records_audit(self, auth_client):
        create = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "cold-start", "persist": True, "storage_size": "5Gi"},
            headers={"X-Request-Id": "req-cold-start"},
        )
        sandbox_id = create.json()["id"]

        async with _test_session_factory() as session:
            sandbox = await session.get(Sandbox, sandbox_id)
            sandbox.status = SandboxStatus.COLD
            sandbox.storage_backend_mode = StorageBackendMode.STANDARD_SNAPSHOT
            sandbox.snapshot_k8s_volume_snapshot_name = f"{sandbox_id}-workspace-snapshot"
            sandbox.pending_operation = None
            session.add(sandbox)
            await session.commit()

        resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/start", headers={"X-Request-Id": "req-cold-start"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cold"
        assert data["pending_operation"] == "restoring"

        async with _test_session_factory() as session:
            events = (
                (
                    await session.execute(
                        select(AuditEvent).where(
                            AuditEvent.target_id == sandbox_id,
                            AuditEvent.action.in_(["sandbox.restore_on_start", "sandbox.start"]),
                        )
                    )
                )
                .scalars()
                .all()
            )
        actions = {event.action for event in events}
        assert "sandbox.restore_on_start" in actions
        assert "sandbox.start" in actions

    async def test_restore_route_is_not_available(self, auth_client):
        create = await auth_client.post(
            "/v1/sandboxes",
            json={"template": "aio-sandbox-tiny", "name": "no-restore-route", "persist": True, "storage_size": "5Gi"},
        )
        sandbox_id = create.json()["id"]

        resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/restore")
        assert resp.status_code == 404
