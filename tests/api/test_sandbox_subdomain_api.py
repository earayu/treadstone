"""API tests for authenticated sandbox subdomain routing."""

from __future__ import annotations

import json
import logging
from io import StringIO
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.middleware.request_logging import request_logger
from treadstone.models.audit_event import AuditEvent
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as client:
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


def _enable_subdomain(monkeypatch, domain: str = "sandbox.localhost", app_base_url: str = "https://app.localhost"):
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
    monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.async_session", _test_session_factory)


async def _create_ready_sandbox(auth_client: AsyncClient, name: str = "mybox") -> str:
    create_resp = await auth_client.post("/v1/sandboxes", json={"template": "aio-sandbox-tiny", "name": name})
    sandbox_id = create_resp.json()["id"]
    async with _test_session_factory() as session:
        sandbox = await session.get(Sandbox, sandbox_id)
        sandbox.status = SandboxStatus.READY.value
        sandbox.k8s_sandbox_name = sandbox.id
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
        sandbox_id = await _create_ready_sandbox(auth_client)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        original_handlers = list(request_logger.handlers)
        request_logger.handlers = [handler]

        try:
            resp = await auth_client.get(f"https://sandbox-{sandbox_id}.sandbox.localhost/", follow_redirects=False)
        finally:
            request_logger.handlers = original_handlers

        assert resp.status_code == 303
        location = resp.headers["location"]
        parsed = urlparse(location)
        assert parsed.netloc == "app.localhost"
        assert parsed.path == "/v1/browser/bootstrap"
        assert parse_qs(parsed.query)["return_to"] == [f"https://sandbox-{sandbox_id}.sandbox.localhost/"]

        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        assert payload["route_kind"] == "subdomain_http"
        assert payload["sandbox_id"] == sandbox_id

    async def test_logged_in_user_can_bootstrap_and_proxy(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        mock_client, captured = _capture_mock()
        auth_client.cookies.set(
            "session",
            "sandbox-app-session",
            domain=f"sandbox-{sandbox_id}.sandbox.localhost",
            path="/",
        )
        auth_client.cookies.set("prefs", "a b", domain=f"sandbox-{sandbox_id}.sandbox.localhost", path="/")

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                bootstrap = await auth_client.get(
                    f"https://sandbox-{sandbox_id}.sandbox.localhost/",
                    follow_redirects=True,
                )
                resp = await auth_client.get(
                    f"https://sandbox-{sandbox_id}.sandbox.localhost/",
                    headers={"Authorization": "Bearer app-token"},
                )

        assert bootstrap.status_code == 200
        assert resp.status_code == 200
        assert f"{sandbox_id}.default.svc.cluster.local:8080/" in captured["url"]
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
                async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as client:
                    resp = await client.get(open_link, follow_redirects=True)
                    followup = await client.get(
                        f"https://sandbox-{sandbox_id}.sandbox.localhost/",
                        follow_redirects=True,
                    )

        assert resp.status_code == 200
        assert followup.status_code == 200

        status_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is True
        assert "open_link" not in status_resp.json()

        async with _test_session_factory() as session:
            events = (
                (await session.execute(select(AuditEvent).where(AuditEvent.action == "sandbox.web_link.open")))
                .scalars()
                .all()
            )

        assert len(events) == 1
        assert events[0].result == "success"
        assert events[0].target_id == sandbox_id

    async def test_enabling_existing_web_link_returns_same_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        second = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        assert first == second

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as client:
            first_resp = await client.get(first, follow_redirects=False)
            second_resp = await client.get(second, follow_redirects=False)

        assert first_resp.status_code == 303
        assert second_resp.status_code == 303

    async def test_delete_web_link_revokes_open_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        open_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}/web-link")
        status_resp = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as browser:
            open_resp = await browser.get(open_link, follow_redirects=False)

        assert delete_resp.status_code == 204
        assert status_resp.status_code == 200
        assert status_resp.json()["enabled"] is False
        assert open_resp.status_code == 401

        async with _test_session_factory() as session:
            events = (
                (await session.execute(select(AuditEvent).where(AuditEvent.action == "sandbox.web_link.open")))
                .scalars()
                .all()
            )

        assert len(events) == 1
        assert events[0].result == "failure"
        assert events[0].error_code == "sandbox_web_link_invalid"

    async def test_recreate_web_link_after_delete_returns_new_active_link(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        delete_resp = await auth_client.delete(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_resp = await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_link = second_resp.json()["open_link"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as browser:
            first_open = await browser.get(first_link, follow_redirects=False)
            second_open = await browser.get(second_link, follow_redirects=False)

        assert delete_resp.status_code == 204
        assert second_resp.status_code == 200
        assert second_link != first_link
        assert first_open.status_code == 401
        assert second_open.status_code == 303

    async def test_enabling_existing_web_link_preserves_last_used_at(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        first_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as browser:
            await browser.get(first_link, follow_redirects=False)

        first_status = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")
        second_link = (await auth_client.post(f"/v1/sandboxes/{sandbox_id}/web-link")).json()["open_link"]
        second_status = await auth_client.get(f"/v1/sandboxes/{sandbox_id}/web-link")

        assert first_status.status_code == 200
        assert first_status.json()["last_used_at"] is not None
        assert second_link == first_link
        assert second_status.status_code == 200
        assert second_status.json()["last_used_at"] == first_status.json()["last_used_at"]

    async def test_unauthenticated_browser_redirects_to_spa_signin(self, auth_client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        sandbox_id = await _create_ready_sandbox(auth_client)
        sandbox_url = f"https://sandbox-{sandbox_id}.sandbox.localhost/"

        async with AsyncClient(transport=ASGITransport(app=app), base_url="https://app.localhost") as browser:
            step1 = await browser.get(sandbox_url, follow_redirects=False)
            assert step1.status_code == 303
            bootstrap_loc = urlparse(step1.headers["location"])
            assert bootstrap_loc.path == "/v1/browser/bootstrap"
            assert parse_qs(bootstrap_loc.query)["return_to"] == [sandbox_url]

            step2 = await browser.get(step1.headers["location"], follow_redirects=False)
            assert step2.status_code == 303
            signin_loc = urlparse(step2.headers["location"])
            assert signin_loc.path == "/auth/sign-in"
            assert sandbox_url in parse_qs(signin_loc.query)["return_to"][0]

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
