"""API tests for authenticated sandbox subdomain routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.sandbox import Sandbox, SandboxStatus
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as client:
        await client.post("/v1/auth/register", json={"email": "sandbox@test.com", "password": "Pass123!"})
        await client.post("/v1/auth/login", json={"email": "sandbox@test.com", "password": "Pass123!"})
        yield client


def _capture_mock():
    captured: dict = {}
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({"content-type": "text/html"})

    async def empty_aiter():
        yield b"ok"

    mock_resp.aiter_bytes = empty_aiter

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False

    def capture_build(method, url, headers, content):
        captured["url"] = str(url)
        captured["method"] = method
        captured["headers"] = dict(headers)
        return httpx.Request(method, url)

    mock_client.build_request.side_effect = capture_build
    mock_client.send.return_value = mock_resp
    return mock_client, captured


def _enable_subdomain(monkeypatch, domain: str = "sandbox.localhost", api_base_url: str = "http://api.localhost"):
    monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", domain)
    monkeypatch.setenv("TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX", "sandbox-")
    monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "default")
    monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "8080")
    monkeypatch.setenv("TREADSTONE_API_BASE_URL", api_base_url)
    monkeypatch.setenv("TREADSTONE_JWT_SECRET", "test-jwt-secret-should-be-32-bytes!")
    from treadstone.config import Settings

    s = Settings()
    monkeypatch.setattr("treadstone.api.browser.settings", s)
    monkeypatch.setattr("treadstone.api.sandboxes.settings", s)
    monkeypatch.setattr("treadstone.core.users.settings", s)
    monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.settings", s)
    monkeypatch.setattr("treadstone.services.sandbox_service.settings", s)
    monkeypatch.setattr("treadstone.services.browser_auth.settings", s)
    monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)
    monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.async_session", _test_session_factory)


async def _create_ready_sandbox(auth_client: AsyncClient, name: str = "mybox") -> str:
    create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": name})
    sandbox_id = create_resp.json()["id"]
    async with _test_session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.status = SandboxStatus.READY.value
        sandbox.k8s_sandbox_name = sandbox.name
        session.add(sandbox)
        await session.commit()
    return sandbox_id


class TestSubdomainDisabled:
    async def test_normal_routes_work_when_disabled(self, db_session, monkeypatch):
        monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", "")
        from treadstone.config import Settings

        s = Settings()
        monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.settings", s)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSubdomainRouting:
    async def test_subdomain_without_cookie_redirects_to_bootstrap(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        await _create_ready_sandbox(auth_client)

        resp = await auth_client.get("http://sandbox-mybox.sandbox.localhost/", follow_redirects=False)

        assert resp.status_code == 303
        location = resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.netloc == "api.localhost"
        assert parsed.path == "/v1/browser/bootstrap"
        assert parse_qs(parsed.query)["return_to"] == ["http://sandbox-mybox.sandbox.localhost/"]

    async def test_logged_in_user_can_bootstrap_and_proxy(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        await _create_ready_sandbox(auth_client)
        mock_client, captured = _capture_mock()
        auth_client.cookies.set("session", "sandbox-app-session", domain="sandbox-mybox.sandbox.localhost", path="/")
        auth_client.cookies.set("prefs", "a b", domain="sandbox-mybox.sandbox.localhost", path="/")

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                bootstrap = await auth_client.get("http://sandbox-mybox.sandbox.localhost/", follow_redirects=True)
                resp = await auth_client.get(
                    "http://sandbox-mybox.sandbox.localhost/",
                    headers={"Authorization": "Bearer app-token"},
                )

        assert bootstrap.status_code == 200
        assert resp.status_code == 200
        assert "mybox.default.svc.cluster.local:8080/" in captured["url"]
        outgoing_headers = {k.lower(): v for k, v in captured["headers"].items()}
        assert outgoing_headers["authorization"] == "Bearer app-token"
        cookie_header = {k.lower(): v for k, v in captured["headers"].items()}.get("cookie", "")
        assert "ts_bui=" not in cookie_header

    async def test_open_link_allows_unauthenticated_browser_access(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        link_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")
        open_link = link_resp.json()["open_link"]

        mock_client, _ = _capture_mock()
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as client:
                    resp = await client.get(open_link, follow_redirects=True)
                    followup = await client.get("http://sandbox-mybox.sandbox.localhost/", follow_redirects=True)

        assert resp.status_code == 200
        assert followup.status_code == 200

        status_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is True
        assert "open_link" not in status_resp.json()

    async def test_recreating_web_link_invalidates_previous_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        second = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        assert first != second

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as client:
            first_resp = await client.get(first, follow_redirects=False)
            second_resp = await client.get(second, follow_redirects=False)

        assert first_resp.status_code == 401
        assert second_resp.status_code == 303

    async def test_delete_web_link_revokes_open_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        open_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}/web-link")
        status_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as browser:
            open_resp = await browser.get(open_link, follow_redirects=False)

        assert delete_resp.status_code == 204
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is False
        assert open_resp.status_code == 401

    async def test_recreate_web_link_after_delete_returns_new_active_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_link = second_resp.json()["open_link"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as browser:
            first_open = await browser.get(first_link, follow_redirects=False)
            second_open = await browser.get(second_link, follow_redirects=False)

        assert delete_resp.status_code == 204
        assert second_resp.status_code == 200
        assert second_link != first_link
        assert first_open.status_code == 401
        assert second_open.status_code == 303

    async def test_rotating_web_link_clears_last_used_at(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as browser:
            await browser.get(first_link, follow_redirects=False)

        first_status = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        second_status = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")

        assert first_status.status_code == 200
        assert first_status.json()["last_used_at"] is not None
        assert second_link != first_link
        assert second_status.status_code == 200
        assert second_status.json()["last_used_at"] is None

    async def test_browser_login_page_can_log_in_and_continue(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        await _create_ready_sandbox(auth_client)
        mock_client, _ = _capture_mock()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://api.localhost") as browser:
            first = await browser.get("http://sandbox-mybox.sandbox.localhost/", follow_redirects=False)
            bootstrap_url = first.headers["location"]
            bootstrap = await browser.get(bootstrap_url, follow_redirects=False)
            login_url = bootstrap.headers["location"]
            login_page = await browser.get(login_url)
            assert login_page.status_code == 200

            with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
                with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                    final = await browser.post(
                        "http://api.localhost/v1/browser/login",
                        data={
                            "email": "sandbox@test.com",
                            "password": "Pass123!",
                            "return_to": "http://sandbox-mybox.sandbox.localhost/",
                        },
                        follow_redirects=True,
                    )

        assert final.status_code == 200

    async def test_non_sandbox_subdomain_falls_through(self, db_session, monkeypatch):
        _enable_subdomain(monkeypatch)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health", headers={"Host": "api.sandbox.localhost:8000"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_exact_sandbox_domain_falls_through(self, db_session, monkeypatch):
        _enable_subdomain(monkeypatch)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health", headers={"Host": "sandbox.localhost:8000"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
