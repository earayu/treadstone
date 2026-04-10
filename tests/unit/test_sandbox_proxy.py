"""Unit tests for treadstone.services.sandbox_proxy helpers."""

from treadstone.services.sandbox_proxy import (
    _filter_request_headers,
    _filter_response_headers,
    _is_x_sandbox_vendor_header,
    build_sandbox_url,
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

    def test_strips_all_x_sandbox_prefixed_headers_case_insensitive(self):
        h = {
            "X-Sandbox-Port": "9999",
            "x-sandbox-namespace": "other-ns",
            "X-Sandbox-ID": "evil",
            "X-Sandbox-Custom": "noise",
            "x-forwarded-for": "1.2.3.4",
        }
        filtered = _filter_request_headers(h)
        for k in filtered:
            assert not _is_x_sandbox_vendor_header(k)
        assert filtered.get("x-forwarded-for") == "1.2.3.4"


class TestFilterResponseHeaders:
    def test_removes_hop_by_hop(self):
        import httpx

        h = httpx.Headers({"content-type": "text/html", "transfer-encoding": "chunked", "x-custom": "yes"})
        filtered = _filter_response_headers(h)
        assert "transfer-encoding" not in filtered
        assert filtered["content-type"] == "text/html"
        assert filtered["x-custom"] == "yes"
