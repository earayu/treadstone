"""API tests for the sandbox proxy router at /v1/sandboxes/{id}/proxy/."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/v1/auth/register", json={"email": "proxy@test.com", "password": "Pass123!"})
        async with _test_session_factory() as session:
            user = (await session.execute(select(User).where(User.email == "proxy@test.com"))).unique().scalar_one()
            user.is_verified = True
            session.add(user)
            await session.commit()
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
    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-missing"})
    api_key = key_resp.json()["key"]
    resp = await auth_client.get(
        "/v1/sandboxes/sb-nonexistent1234/proxy/healthz",
        headers={"Authorization": f"Bearer {api_key}"},
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

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-stopped"})
    api_key = key_resp.json()["key"]

    resp = await auth_client.get(
        f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
        headers={"Authorization": f"Bearer {api_key}"},
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
    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-ready"})
    api_key = key_resp.json()["key"]

    with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
        resp = await auth_client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {api_key}"},
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


async def test_proxy_api_key_without_data_scope_returns_403(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-api-key-sb"},
    )
    sandbox_id = create_resp.json()["id"]
    key_resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={"name": "proxy-key", "scope": {"control_plane": True, "data_plane": {"mode": "none"}}},
    )
    api_key = key_resp.json()["key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_proxy_selected_scope_mismatch_returns_403(auth_client):
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

    key_resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={
            "name": "proxy-selected",
            "scope": {
                "control_plane": False,
                "data_plane": {"mode": "selected", "sandbox_ids": [first_id]},
            },
        },
    )
    api_key = key_resp.json()["key"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{second_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_proxy_selected_scope_allows_granted_sandbox(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-selected-hit"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post(
        "/v1/auth/api-keys",
        json={
            "name": "proxy-selected-hit",
            "scope": {
                "control_plane": False,
                "data_plane": {"mode": "selected", "sandbox_ids": [sandbox_id]},
            },
        },
    )
    api_key = key_resp.json()["key"]
    mock_client = _mock_upstream(body=b'{"selected": true}', headers={"content-type": "application/json"})

    with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
                headers={"Authorization": f"Bearer {api_key}"},
            )

    assert resp.status_code == 200
    assert resp.json() == {"selected": True}


async def test_proxy_deleted_api_key_returns_401(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-deleted-key"},
    )
    sandbox_id = create_resp.json()["id"]

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-delete"})
    key_id = key_resp.json()["id"]
    api_key = key_resp.json()["key"]
    await auth_client.delete(f"/v1/auth/api-keys/{key_id}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth_invalid"


async def test_proxy_forwards_query_string(auth_client):
    """Query params must be forwarded to the sandbox so MCP SSE ?sessionId= works."""
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-qs-sb"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-qs"})
    api_key = key_resp.json()["key"]

    captured_paths: list[str] = []

    async def capturing_proxy_http_request(*, method, sandbox_id, path, **kwargs):
        captured_paths.append(path)
        return 200, {"content-type": "text/plain"}, _mock_upstream(body=b"ok").send.return_value

    with patch("treadstone.api.sandbox_proxy.proxy_http_request", side_effect=capturing_proxy_http_request):
        resp = await auth_client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/mcp?sessionId=abc123&stream=1",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    assert resp.status_code == 200
    assert len(captured_paths) == 1
    assert "sessionId=abc123" in captured_paths[0]
    assert "stream=1" in captured_paths[0]


async def test_proxy_ignores_namespace_and_port_override_headers(auth_client):
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-routing-boundary"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-routing-boundary"})
    api_key = key_resp.json()["key"]

    proxy_calls: list[dict] = []

    async def capturing_proxy_http_request(**kwargs):
        proxy_calls.append(kwargs)
        return 200, {"content-type": "text/plain"}, _mock_upstream(body=b"ok").send.return_value

    with patch("treadstone.api.sandbox_proxy.proxy_http_request", side_effect=capturing_proxy_http_request):
        resp = await auth_client.get(
            f"/v1/sandboxes/{sandbox_id}/proxy/healthz",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Sandbox-Namespace": "attacker-ns",
                "X-Sandbox-Port": "9001",
            },
        )

    assert resp.status_code == 200
    assert len(proxy_calls) == 1
    assert proxy_calls[0]["namespace"] != "attacker-ns"
    assert proxy_calls[0]["port"] != 9001


def _make_ws_scope(path: str, headers: list[tuple[bytes, bytes]], query_string: bytes = b"") -> dict:
    """Build a minimal ASGI WebSocket scope for direct ASGI dispatch in tests."""
    return {
        "type": "websocket",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "scheme": "ws",
        "query_string": query_string,
        "headers": headers,
        "subprotocols": [],
        "extensions": {},
        "state": {},
    }


async def _run_ws_asgi(scope: dict) -> list[dict]:
    """Drive a WebSocket ASGI request and collect all sent messages."""
    import asyncio

    sends: list[dict] = []
    connected = False

    async def receive():
        nonlocal connected
        if not connected:
            connected = True
            return {"type": "websocket.connect"}
        await asyncio.sleep(999)

    async def send_fn(msg: dict) -> None:
        sends.append(msg)

    await app(scope, receive, send_fn)
    return sends


async def test_proxy_ws_no_auth_closes_1008(auth_client):
    """WebSocket proxy must close with code 1008 when no API key is provided."""
    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-ws-noauth"},
    )
    sandbox_id = create_resp.json()["id"]

    scope = _make_ws_scope(f"/v1/sandboxes/{sandbox_id}/proxy/mcp", headers=[])
    sends = await _run_ws_asgi(scope)

    close_msgs = [m for m in sends if m.get("type") == "websocket.close"]
    assert close_msgs, "Expected a websocket.close message"
    assert close_msgs[0]["code"] == 1008


async def test_proxy_ws_with_api_key_header_proxies(auth_client, monkeypatch):
    """WebSocket proxy authenticates via Authorization header and calls proxy_websocket."""
    # ws_proxy uses async_session directly, so patch to use the test DB factory.
    monkeypatch.setattr("treadstone.api.sandbox_proxy.async_session", _test_session_factory)

    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-ws-auth"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-ws-key"})
    api_key = key_resp.json()["key"]

    proxy_calls: list[dict] = []

    async def capturing_proxy_websocket(**kwargs):
        proxy_calls.append(kwargs)

    headers = [(b"authorization", f"Bearer {api_key}".encode())]
    scope = _make_ws_scope(f"/v1/sandboxes/{sandbox_id}/proxy/mcp", headers=headers)

    with patch("treadstone.api.sandbox_proxy.proxy_websocket", side_effect=capturing_proxy_websocket):
        await _run_ws_asgi(scope)

    assert len(proxy_calls) == 1, f"proxy_websocket was called {len(proxy_calls)} times; expected 1"
    assert proxy_calls[0]["path"] == "mcp"


async def test_proxy_ws_token_param_auth(auth_client, monkeypatch):
    """WebSocket proxy accepts API key via ?token= query param and strips it upstream."""
    monkeypatch.setattr("treadstone.api.sandbox_proxy.async_session", _test_session_factory)

    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-ws-token-param"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-ws-token"})
    api_key = key_resp.json()["key"]

    proxy_calls: list[dict] = []

    async def capturing_proxy_websocket(**kwargs):
        proxy_calls.append(kwargs)

    qs = f"token={api_key}&sessionId=xyz".encode()
    scope = _make_ws_scope(f"/v1/sandboxes/{sandbox_id}/proxy/mcp", headers=[], query_string=qs)

    with patch("treadstone.api.sandbox_proxy.proxy_websocket", side_effect=capturing_proxy_websocket):
        await _run_ws_asgi(scope)

    assert len(proxy_calls) == 1, f"proxy_websocket was called {len(proxy_calls)} times; expected 1"
    upstream_path = proxy_calls[0]["path"]
    # token must not be forwarded to the upstream pod
    assert "token=" not in upstream_path
    # other query params must survive
    assert "sessionId=xyz" in upstream_path


async def test_proxy_ws_ignores_namespace_and_port_override_headers(auth_client, monkeypatch):
    monkeypatch.setattr("treadstone.api.sandbox_proxy.async_session", _test_session_factory)

    create_resp = await auth_client.post(
        "/v1/sandboxes",
        json={"template": "aio-sandbox-tiny", "name": "proxy-ws-routing-boundary"},
    )
    sandbox_id = create_resp.json()["id"]

    async with _test_session_factory() as session:
        from treadstone.models.sandbox import Sandbox

        sb = await session.get(Sandbox, sandbox_id)
        sb.status = "ready"
        session.add(sb)
        await session.commit()

    key_resp = await auth_client.post("/v1/auth/api-keys", json={"name": "proxy-ws-routing-boundary"})
    api_key = key_resp.json()["key"]

    proxy_calls: list[dict] = []

    async def capturing_proxy_websocket(**kwargs):
        proxy_calls.append(kwargs)

    headers = [
        (b"authorization", f"Bearer {api_key}".encode()),
        (b"x-sandbox-namespace", b"attacker-ns"),
        (b"x-sandbox-port", b"9001"),
    ]
    scope = _make_ws_scope(f"/v1/sandboxes/{sandbox_id}/proxy/mcp", headers=headers)

    with patch("treadstone.api.sandbox_proxy.proxy_websocket", side_effect=capturing_proxy_websocket):
        await _run_ws_asgi(scope)

    assert len(proxy_calls) == 1
    assert proxy_calls[0]["namespace"] != "attacker-ns"
    assert proxy_calls[0]["port"] != 9001
