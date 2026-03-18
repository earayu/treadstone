"""API tests for the sandbox proxy router."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from treadstone.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _mock_upstream(body: bytes = b"", status: int = 200, headers: dict | None = None):
    """Build a mock httpx client that returns a canned response."""
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


def _capture_mock_upstream():
    """Build a mock that captures the target URL."""
    captured: dict = {}
    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.headers = httpx.Headers({})

    async def empty_aiter():
        yield b""

    mock_resp.aiter_bytes = empty_aiter

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.is_closed = False

    def capture_build(method, url, headers, content):
        captured["url"] = str(url)
        captured["headers"] = dict(headers)
        return httpx.Request(method, url)

    mock_client.build_request.side_effect = capture_build
    mock_client.send.return_value = mock_resp
    return mock_client, captured


# ── Header-based routing (SDK-compatible) ────────────────────────────────────


class TestHeaderBasedProxy:
    async def test_invalid_namespace_returns_400(self, client: AsyncClient):
        resp = await client.get(
            "/api/sandbox/sb-1/v1/execute",
            headers={"X-Sandbox-Namespace": "bad namespace!"},
        )
        assert resp.status_code == 400
        assert "namespace" in resp.json()["detail"].lower()

    async def test_invalid_port_returns_400(self, client: AsyncClient):
        resp = await client.get(
            "/api/sandbox/sb-1/v1/execute",
            headers={"X-Sandbox-Port": "xyz"},
        )
        assert resp.status_code == 400
        assert "port" in resp.json()["detail"].lower()


# ── Path-based routing (browser-friendly) ────────────────────────────────────


class TestPathBasedProxy:
    async def test_proxy_returns_upstream_response(self, client: AsyncClient):
        mock_client = _mock_upstream(
            body=b'{"stdout":"hello","stderr":"","exit_code":0}',
            headers={"content-type": "application/json"},
        )
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            resp = await client.post(
                "/api/sandbox/sb-test/v1/execute",
                json={"command": "echo hello"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"stdout": "hello", "stderr": "", "exit_code": 0}

    async def test_upstream_connection_error_returns_502(self, client: AsyncClient):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.build_request.return_value = httpx.Request("GET", "http://fake")
        mock_client.send.side_effect = httpx.ConnectError("connection refused")

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            resp = await client.get("/api/sandbox/sb-down/healthz")
        assert resp.status_code == 502
        assert "sb-down" in resp.json()["detail"]

    async def test_correct_target_url_from_path(self, client: AsyncClient):
        mock_client, captured = _capture_mock_upstream()
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            await client.get(
                "/api/sandbox/sb-xyz/v1/execute",
                headers={"X-Sandbox-Namespace": "staging", "X-Sandbox-Port": "9090"},
            )
        assert captured["url"] == "http://sb-xyz.staging.svc.cluster.local:9090/v1/execute"

    async def test_host_header_stripped(self, client: AsyncClient):
        mock_client, captured = _capture_mock_upstream()
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            await client.get(
                "/api/sandbox/sb-test/healthz",
                headers={"Host": "evil.com"},
            )
        assert "host" not in {k.lower() for k in captured["headers"]}

    async def test_path_sandbox_id_overrides_header(self, client: AsyncClient):
        mock_client, captured = _capture_mock_upstream()
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            await client.get(
                "/api/sandbox/from-path/healthz",
                headers={"X-Sandbox-ID": "from-header"},
            )
        assert "from-path" in captured["url"]
        assert "from-header" not in captured["url"]

    async def test_default_namespace_and_port_from_settings(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "my-ns")
        monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "7777")
        from treadstone.config import Settings

        s = Settings()
        monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)

        mock_client, captured = _capture_mock_upstream()
        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            await client.get("/api/sandbox/sb-1/v1/docs")
        assert "sb-1.my-ns.svc.cluster.local:7777" in captured["url"]

    async def test_invalid_sandbox_id_returns_400(self, client: AsyncClient):
        resp = await client.get("/api/sandbox/bad id!/v1/execute")
        assert resp.status_code == 400
        assert "sandbox id" in resp.json()["detail"].lower()
