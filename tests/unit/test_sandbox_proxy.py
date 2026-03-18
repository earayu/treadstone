"""Unit tests for treadstone.services.sandbox_proxy helpers."""

import pytest

from treadstone.services.sandbox_proxy import (
    _filter_request_headers,
    _filter_response_headers,
    build_sandbox_url,
    resolve_routing,
)


class TestBuildSandboxUrl:
    def test_default_namespace_and_port(self, monkeypatch):
        monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "default")
        monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "8080")
        from treadstone.config import Settings

        s = Settings()
        monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)

        url = build_sandbox_url("my-sandbox", "v1/execute")
        assert url == "http://my-sandbox.default.svc.cluster.local:8080/v1/execute"

    def test_custom_namespace_and_port(self):
        url = build_sandbox_url("sb-1", "hello", namespace="prod", port=9090)
        assert url == "http://sb-1.prod.svc.cluster.local:9090/hello"

    def test_ws_scheme(self):
        url = build_sandbox_url("sb-1", "vnc", namespace="ns", port=6080, scheme="ws")
        assert url == "ws://sb-1.ns.svc.cluster.local:6080/vnc"

    def test_strips_leading_slash(self):
        url = build_sandbox_url("sb-1", "/some/path", namespace="ns", port=8080)
        assert url == "http://sb-1.ns.svc.cluster.local:8080/some/path"


class TestResolveRouting:
    def test_from_headers(self):
        result = resolve_routing(
            {
                "x-sandbox-id": "sb-abc",
                "x-sandbox-namespace": "dev",
                "x-sandbox-port": "9090",
            }
        )
        assert result == {"sandbox_id": "sb-abc", "namespace": "dev", "port": 9090}

    def test_path_sandbox_id_takes_priority(self):
        result = resolve_routing(
            {"x-sandbox-id": "from-header"},
            path_sandbox_id="from-path",
        )
        assert result["sandbox_id"] == "from-path"

    def test_path_sandbox_id_with_namespace_from_header(self):
        result = resolve_routing(
            {"x-sandbox-namespace": "staging", "x-sandbox-port": "9090"},
            path_sandbox_id="sb-1",
        )
        assert result == {"sandbox_id": "sb-1", "namespace": "staging", "port": 9090}

    def test_missing_sandbox_id_raises(self):
        with pytest.raises(ValueError, match="X-Sandbox-ID header is required"):
            resolve_routing({})

    def test_invalid_sandbox_id_raises(self):
        with pytest.raises(ValueError, match="Invalid sandbox ID format"):
            resolve_routing({}, path_sandbox_id="bad id!")

    def test_invalid_namespace_raises(self):
        with pytest.raises(ValueError, match="Invalid namespace format"):
            resolve_routing(
                {
                    "x-sandbox-id": "sb-1",
                    "x-sandbox-namespace": "bad namespace!",
                }
            )

    def test_hyphenated_namespace_ok(self):
        result = resolve_routing(
            {
                "x-sandbox-id": "sb-1",
                "x-sandbox-namespace": "my-namespace",
            }
        )
        assert result["namespace"] == "my-namespace"

    def test_invalid_port_raises(self):
        with pytest.raises(ValueError, match="Invalid port format"):
            resolve_routing(
                {
                    "x-sandbox-id": "sb-1",
                    "x-sandbox-port": "not-a-number",
                }
            )

    def test_defaults_come_from_settings(self, monkeypatch):
        monkeypatch.setenv("TREADSTONE_SANDBOX_NAMESPACE", "staging")
        monkeypatch.setenv("TREADSTONE_SANDBOX_PORT", "9999")
        from treadstone.config import Settings

        s = Settings()
        monkeypatch.setattr("treadstone.services.sandbox_proxy.settings", s)

        result = resolve_routing({"x-sandbox-id": "sb-1"})
        assert result["namespace"] == "staging"
        assert result["port"] == 9999


class TestFilterRequestHeaders:
    def test_removes_hop_by_hop(self):
        h = {"host": "example.com", "connection": "keep-alive", "x-custom": "yes"}
        filtered = _filter_request_headers(h)
        assert "host" not in filtered
        assert "connection" not in filtered
        assert filtered["x-custom"] == "yes"

    def test_forces_identity_encoding(self):
        filtered = _filter_request_headers({"accept-encoding": "gzip, br"})
        assert filtered["accept-encoding"] == "identity"


class TestFilterResponseHeaders:
    def test_removes_hop_by_hop(self):
        import httpx

        h = httpx.Headers({"content-type": "text/html", "transfer-encoding": "chunked", "x-custom": "yes"})
        filtered = _filter_response_headers(h)
        assert "transfer-encoding" not in filtered
        assert filtered["content-type"] == "text/html"
        assert filtered["x-custom"] == "yes"
