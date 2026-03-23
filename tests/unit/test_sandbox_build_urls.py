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


def test_build_urls_web_omits_port_for_plain_localhost(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", SimpleNamespace(sandbox_domain="sandbox.localhost"))
    sb = SimpleNamespace(id="1", name="sbx")
    urls = _build_urls(sb, "http://localhost/")
    assert urls["web"] == "http://sbx.sandbox.localhost"
    assert urls["proxy"] == "http://localhost/v1/sandboxes/1/proxy"


def test_build_urls_web_includes_port_for_dev_server(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", SimpleNamespace(sandbox_domain="sandbox.localhost"))
    sb = SimpleNamespace(id="1", name="sbx")
    urls = _build_urls(sb, "http://localhost:8000/")
    assert urls["web"] == "http://sbx.sandbox.localhost:8000"


def test_build_urls_web_includes_port_for_port_forward(monkeypatch) -> None:
    monkeypatch.setattr("treadstone.api.sandboxes.settings", SimpleNamespace(sandbox_domain="sandbox.localhost"))
    sb = SimpleNamespace(id="1", name="sbx")
    urls = _build_urls(sb, "http://127.0.0.1:12345/")
    assert urls["web"] == "http://sbx.sandbox.localhost:12345"
