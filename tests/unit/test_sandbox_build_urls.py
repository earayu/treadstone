"""Unit tests for sandbox API URL construction (web vs proxy links)."""

from types import SimpleNamespace

import pytest

from treadstone.api.sandboxes import _build_urls, _web_port_suffix


@pytest.mark.parametrize(
    ("api_base", "expected_suffix"),
    [
        ("http://localhost/", ""),
        ("http://localhost", ""),
        ("https://localhost/", ""),
        ("http://127.0.0.1/", ""),
        ("http://localhost:80/", ""),
        ("https://localhost:443/", ""),
        ("http://localhost:8000/", ":8000"),
        ("http://127.0.0.1:8080/", ":8080"),
        ("https://api.example.com:8443/v1/", ":8443"),
        ("http://[::1]:9090/", ":9090"),
    ],
)
def test_web_port_suffix(api_base: str, expected_suffix: str) -> None:
    assert _web_port_suffix(api_base) == expected_suffix


def _fake_settings(**overrides):
    defaults = {"sandbox_domain": "sandbox.localhost", "sandbox_subdomain_prefix": "sandbox-"}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_build_urls_web_omits_port_for_plain_localhost(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", _fake_settings())
    sb = SimpleNamespace(id="sb123", name="sbx")
    urls = _build_urls(sb, "http://localhost/")
    assert urls["web"] == "http://sandbox-sb123.sandbox.localhost"
    assert urls["proxy"] == "http://localhost/v1/sandboxes/sb123/proxy"
    assert urls["mcp"] == "http://localhost/v1/sandboxes/sb123/proxy/mcp"


def test_build_urls_web_includes_port_for_dev_server(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", _fake_settings())
    sb = SimpleNamespace(id="sb123", name="sbx")
    urls = _build_urls(sb, "http://localhost:8000/")
    assert urls["web"] == "http://sandbox-sb123.sandbox.localhost:8000"
    assert urls["mcp"] == "http://localhost:8000/v1/sandboxes/sb123/proxy/mcp"


def test_build_urls_web_includes_port_for_port_forward(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", _fake_settings())
    sb = SimpleNamespace(id="sb123", name="sbx")
    urls = _build_urls(sb, "http://127.0.0.1:12345/")
    assert urls["web"] == "http://sandbox-sb123.sandbox.localhost:12345"
    assert urls["mcp"] == "http://127.0.0.1:12345/v1/sandboxes/sb123/proxy/mcp"


def test_build_urls_prod_domain(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", _fake_settings(sandbox_domain="treadstone-ai.dev"))
    sb = SimpleNamespace(id="sb123", name="my-project")
    urls = _build_urls(sb, "https://api.treadstone-ai.dev/")
    assert urls["web"] == "https://sandbox-sb123.treadstone-ai.dev"
    assert urls["proxy"] == "https://api.treadstone-ai.dev/v1/sandboxes/sb123/proxy"
    assert urls["mcp"] == "https://api.treadstone-ai.dev/v1/sandboxes/sb123/proxy/mcp"


def test_build_urls_web_none_when_domain_empty(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", _fake_settings(sandbox_domain=""))
    sb = SimpleNamespace(id="sb123", name="sbx")
    urls = _build_urls(sb, "http://localhost/")
    assert urls["web"] is None
    assert urls["mcp"] == "http://localhost/v1/sandboxes/sb123/proxy/mcp"
