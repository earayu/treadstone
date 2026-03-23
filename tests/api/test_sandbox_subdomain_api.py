"""API tests for subdomain-based sandbox routing (prefix-based)."""

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
        return httpx.Request(method, url)

    mock_client.build_request.side_effect = capture_build
    mock_client.send.return_value = mock_resp
    return mock_client, captured


def _enable_subdomain(monkeypatch, domain: str = "sandbox.localhost"):
    monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", domain)
    monkeypatch.setenv("TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX", "sandbox-")
    monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "default")
    monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "8080")
    from treadstone.config import Settings

    s = Settings()
    monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.settings", s)
    monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)


class TestSubdomainDisabled:
    async def test_normal_routes_work_when_disabled(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("TREADSTONE_SANDBOX_DOMAIN", "")
        from treadstone.config import Settings

        s = Settings()
        monkeypatch.setattr("treadstone.middleware.sandbox_subdomain.settings", s)

        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestSubdomainRouting:
    async def test_subdomain_proxies_to_sandbox(self, client: AsyncClient, monkeypatch):
        """sandbox-mybox.sandbox.localhost → mybox.default.svc.cluster.local"""
        _enable_subdomain(monkeypatch)
        mock_client, captured = _capture_mock()

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                resp = await client.get(
                    "/v1/docs",
                    headers={"Host": "sandbox-mybox.sandbox.localhost:8000"},
                )

        assert resp.status_code == 200
        assert "mybox.default.svc.cluster.local:8080/v1/docs" in captured["url"]

    async def test_subdomain_root_path(self, client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        mock_client, captured = _capture_mock()

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                resp = await client.get(
                    "/",
                    headers={"Host": "sandbox-mybox.sandbox.localhost:8000"},
                )

        assert resp.status_code == 200

    async def test_non_sandbox_subdomain_falls_through(self, client: AsyncClient, monkeypatch):
        """api.sandbox.localhost does NOT have the sandbox- prefix → falls through."""
        _enable_subdomain(monkeypatch)
        resp = await client.get(
            "/health",
            headers={"Host": "api.sandbox.localhost:8000"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_non_subdomain_falls_through(self, client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        resp = await client.get(
            "/health",
            headers={"Host": "localhost:8000"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_exact_sandbox_domain_falls_through(self, client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        resp = await client.get(
            "/health",
            headers={"Host": "sandbox.localhost:8000"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_upstream_error_returns_502(self, client: AsyncClient, monkeypatch):
        _enable_subdomain(monkeypatch)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.build_request.return_value = httpx.Request("GET", "http://fake")
        mock_client.send.side_effect = httpx.ConnectError("refused")

        with patch("treadstone.services.sandbox_proxy._http_client", mock_client):
            with patch("treadstone.middleware.sandbox_subdomain.get_http_client", return_value=mock_client):
                resp = await client.get(
                    "/",
                    headers={"Host": "sandbox-down.sandbox.localhost:8000"},
                )

        assert resp.status_code == 502
