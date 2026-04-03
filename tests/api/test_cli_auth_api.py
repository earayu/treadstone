from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from treadstone.api import auth as auth_api
from treadstone.api import cli_auth as cli_auth_api
from treadstone.core.database import Base, get_session
from treadstone.core.users import UserManager, get_user_db, get_user_manager
from treadstone.main import app
from treadstone.models.cli_login_flow import CliLoginFlow
from treadstone.models.user import OAuthAccount, User, utc_now

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


async def _register_user(http_client: AsyncClient, email: str = "u@b.com", password: str = "Pass123!") -> dict:
    resp = await http_client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201
    return resp.json()


async def _create_flow(http_client: AsyncClient) -> dict:
    resp = await http_client.post("/v1/auth/cli/flows")
    assert resp.status_code == 200
    data = resp.json()
    assert "flow_id" in data
    assert "flow_secret" in data
    assert "browser_url" in data
    return data


@pytest.mark.asyncio
async def test_create_flow_returns_flow_data(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        data = await _create_flow(http_client)

    assert data["flow_id"].startswith("clf")
    assert f"http://test/auth/cli/login?flow_id={data['flow_id']}" in data["browser_url"]
    assert f"flow_secret={data['flow_secret']}" in data["browser_url"]
    assert data["poll_interval"] == 2


@pytest.mark.asyncio
async def test_poll_flow_pending(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)
        resp = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_poll_flow_wrong_secret_returns_401(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)
        resp = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": "wrong-secret"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_poll_flow_missing_secret_returns_401(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)
        resp = await http_client.get(f"/v1/auth/cli/flows/{flow['flow_id']}/status")

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_email_login_approves_flow_and_exchange_returns_session(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        await _register_user(http_client)
        flow = await _create_flow(http_client)

        login_resp = await http_client.post(
            "/v1/auth/cli/login",
            data={
                "email": "u@b.com",
                "password": "Pass123!",
                "flow_id": flow["flow_id"],
                "flow_secret": flow["flow_secret"],
            },
        )
        assert login_resp.status_code == 200
        assert login_resp.json()["status"] == "approved"

        poll = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert poll.json()["status"] == "approved"

        exchange = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/exchange",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert exchange.status_code == 200
        assert "session_token" in exchange.json()


@pytest.mark.asyncio
async def test_exchange_marks_flow_as_used(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        await _register_user(http_client)
        flow = await _create_flow(http_client)

        await http_client.post(
            "/v1/auth/cli/login",
            data={
                "email": "u@b.com",
                "password": "Pass123!",
                "flow_id": flow["flow_id"],
                "flow_secret": flow["flow_secret"],
            },
        )
        headers = {"X-Flow-Secret": flow["flow_secret"]}
        await http_client.post(f"/v1/auth/cli/flows/{flow['flow_id']}/exchange", headers=headers)

        second = await http_client.post(f"/v1/auth/cli/flows/{flow['flow_id']}/exchange", headers=headers)
        assert second.status_code == 400
        assert "already been used" in second.json()["error"]["message"]


@pytest.mark.asyncio
async def test_exchange_pending_flow_returns_error(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

        exchange = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/exchange",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert exchange.status_code == 400
        assert "not approved" in exchange.json()["error"]["message"]


@pytest.mark.asyncio
async def test_expired_flow_returns_expired_status(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

    async with _test_session_factory() as session:
        db_flow = (await session.execute(select(CliLoginFlow).where(CliLoginFlow.id == flow["flow_id"]))).scalar_one()
        db_flow.gmt_expires = utc_now() - timedelta(seconds=1)
        session.add(db_flow)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        poll = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
    assert poll.json()["status"] == "expired"


@pytest.mark.asyncio
async def test_cli_login_page_renders(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)
        resp = await http_client.get(
            f"/v1/auth/cli/login?flow_id={flow['flow_id']}&flow_secret={flow['flow_secret']}",
            follow_redirects=False,
        )

    assert resp.status_code == 303
    location = resp.headers["location"]
    assert f"/auth/cli/login?flow_id={flow['flow_id']}" in location
    assert f"flow_secret={flow['flow_secret']}" in location


@pytest.mark.asyncio
async def test_email_login_wrong_password_re_renders_page(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        await _register_user(http_client)
        flow = await _create_flow(http_client)

        resp = await http_client.post(
            "/v1/auth/cli/login",
            data={
                "email": "u@b.com",
                "password": "wrong",
                "flow_id": flow["flow_id"],
                "flow_secret": flow["flow_secret"],
            },
        )

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "bad_request"
    assert body["error"]["message"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_oauth_callback_approves_cli_flow(db_session, monkeypatch):
    """Google OAuth callback with cli_flow_id approves the flow and redirects to SPA."""
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")

    from tests.api.test_oauth_api import FakeOAuthClient

    client = FakeOAuthClient("google", account_id="acct-cli", account_email="cli@example.com")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

        authorize = await http_client.get(
            "/v1/auth/google/authorize",
            params={"cli_flow_id": flow["flow_id"], "cli_flow_secret": flow["flow_secret"]},
            follow_redirects=False,
        )
        assert authorize.status_code == 303

        state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]
        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"code": "oauth-code", "state": state},
            follow_redirects=False,
        )

        assert callback.status_code == 303
        location = callback.headers["location"]
        assert "/auth/cli/login?" in location
        assert "result=approved" in location
        assert callback.cookies.get("session") is None

        poll = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert poll.json()["status"] == "approved"

        exchange = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/exchange",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert exchange.status_code == 200
        assert "session_token" in exchange.json()


@pytest.mark.asyncio
async def test_session_token_from_exchange_is_valid(db_session, monkeypatch):
    """Session token from CLI flow exchange can be used to call authenticated endpoints."""
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        await _register_user(http_client)
        flow = await _create_flow(http_client)

        await http_client.post(
            "/v1/auth/cli/login",
            data={
                "email": "u@b.com",
                "password": "Pass123!",
                "flow_id": flow["flow_id"],
                "flow_secret": flow["flow_secret"],
            },
        )

        exchange = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/exchange",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        token = exchange.json()["session_token"]

        whoami = await http_client.get(
            "/v1/auth/user",
            cookies={"session": token},
        )
        assert whoami.status_code == 200
        assert whoami.json()["email"] == "u@b.com"


@pytest.mark.asyncio
async def test_oauth_callback_with_expired_flow_does_not_create_user(db_session, monkeypatch):
    """P1 regression: expired CLI flow must reject BEFORE creating user/OAuthAccount."""
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")

    from tests.api.test_oauth_api import FakeOAuthClient

    client = FakeOAuthClient("google", account_id="acct-ghost", account_email="ghost@example.com")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

    async with _test_session_factory() as session:
        db_flow = (await session.execute(select(CliLoginFlow).where(CliLoginFlow.id == flow["flow_id"]))).scalar_one()
        db_flow.gmt_expires = utc_now() - timedelta(seconds=1)
        session.add(db_flow)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        authorize = await http_client.get(
            "/v1/auth/google/authorize",
            params={"cli_flow_id": flow["flow_id"], "cli_flow_secret": flow["flow_secret"]},
            follow_redirects=False,
        )
    assert authorize.status_code == 400
    assert authorize.json()["error"]["code"] == "bad_request"
    assert "expired" in authorize.json()["error"]["message"].lower()

    async with _test_session_factory() as session:
        users = (await session.execute(select(User).where(User.email == "ghost@example.com"))).unique().scalars().all()
    assert len(users) == 0, "No user should be created when CLI flow is expired"


@pytest.mark.asyncio
async def test_oauth_access_denied_marks_cli_flow_as_failed(db_session, monkeypatch):
    """P2 regression: provider deny must mark CLI flow as failed and redirect to SPA."""
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")

    from tests.api.test_oauth_api import FakeOAuthClient

    client = FakeOAuthClient("google")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

        authorize = await http_client.get(
            "/v1/auth/google/authorize",
            params={"cli_flow_id": flow["flow_id"], "cli_flow_secret": flow["flow_secret"]},
            follow_redirects=False,
        )
        state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]

        callback = await http_client.get(
            "/v1/auth/google/callback",
            params={"state": state, "error": "access_denied"},
            follow_redirects=False,
        )
        assert callback.status_code == 303
        location = callback.headers["location"]
        assert "/auth/cli/login?" in location
        assert "result=failed" in location
        assert "error=" in location

        poll = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert poll.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_session_based_approve(db_session, monkeypatch):
    """Approve CLI flow using browser session cookie from the /approve endpoint."""
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        reg_resp = await http_client.post("/v1/auth/register", json={"email": "u@b.com", "password": "Pass123!"})
        assert reg_resp.status_code == 201
        session_cookie = reg_resp.cookies.get("session")
        assert session_cookie is not None

        flow = await _create_flow(http_client)

        resp = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/approve",
            cookies={"session": session_cookie},
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        poll = await http_client.get(
            f"/v1/auth/cli/flows/{flow['flow_id']}/status",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert poll.json()["status"] == "approved"

        exchange = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/exchange",
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert exchange.status_code == 200
        assert "session_token" in exchange.json()


@pytest.mark.asyncio
async def test_session_based_approve_requires_auth(db_session, monkeypatch):
    """POST /v1/auth/cli/flows/{flow_id}/approve requires a valid session cookie."""
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)
        resp = await http_client.post(f"/v1/auth/cli/flows/{flow['flow_id']}/approve")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_session_based_approve_is_not_replayable(db_session, monkeypatch):
    """Second call to /approve on an already-approved flow returns 400."""
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        reg_resp = await http_client.post("/v1/auth/register", json={"email": "u@b.com", "password": "Pass123!"})
        session_cookie = reg_resp.cookies.get("session")
        flow = await _create_flow(http_client)

        first = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/approve",
            cookies={"session": session_cookie},
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert first.status_code == 200

        second = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/approve",
            cookies={"session": session_cookie},
            headers={"X-Flow-Secret": flow["flow_secret"]},
        )
        assert second.status_code == 400
        assert "already been used or has expired" in second.json()["error"]["message"]


@pytest.mark.asyncio
async def test_email_login_requires_matching_flow_secret(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        await _register_user(http_client)
        flow = await _create_flow(http_client)

        resp = await http_client.post(
            "/v1/auth/cli/login",
            data={"email": "u@b.com", "password": "Pass123!", "flow_id": flow["flow_id"], "flow_secret": "wrong"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_required"


@pytest.mark.asyncio
async def test_session_based_approve_requires_matching_flow_secret(db_session, monkeypatch):
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        reg_resp = await http_client.post("/v1/auth/register", json={"email": "u@b.com", "password": "Pass123!"})
        session_cookie = reg_resp.cookies.get("session")
        flow = await _create_flow(http_client)

        resp = await http_client.post(
            f"/v1/auth/cli/flows/{flow['flow_id']}/approve",
            cookies={"session": session_cookie},
            headers={"X-Flow-Secret": "wrong"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_required"


@pytest.mark.asyncio
async def test_oauth_authorize_requires_matching_cli_flow_secret(db_session, monkeypatch):
    monkeypatch.setattr(auth_api.settings, "app_base_url", "http://test")
    monkeypatch.setattr(cli_auth_api.settings, "app_base_url", "http://test")

    from tests.api.test_oauth_api import FakeOAuthClient

    client = FakeOAuthClient("google", account_id="acct-cli-secret", account_email="cli-secret@example.com")
    monkeypatch.setattr(auth_api, "get_google_oauth_client", lambda: client, raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http_client:
        flow = await _create_flow(http_client)

        authorize = await http_client.get(
            "/v1/auth/google/authorize",
            params={"cli_flow_id": flow["flow_id"], "cli_flow_secret": "wrong"},
            follow_redirects=False,
        )

    assert authorize.status_code == 401
    assert authorize.json()["error"]["code"] == "auth_required"
