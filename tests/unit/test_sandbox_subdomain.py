"""Unit tests for sandbox subdomain extraction and auth-header stripping."""

from treadstone.middleware.sandbox_subdomain import _strip_internal_auth, extract_sandbox_id


class TestExtractSandboxId:
    """extract_sandbox_id recognises the ``sandbox-`` prefix and strips it."""

    def test_valid_sandbox_subdomain(self):
        assert extract_sandbox_id("sandbox-foobar.treadstone-ai.dev", "treadstone-ai.dev") == "foobar"

    def test_valid_with_port(self):
        assert extract_sandbox_id("sandbox-foobar.sandbox.localhost:8000", "sandbox.localhost") == "foobar"

    def test_case_insensitive(self):
        assert extract_sandbox_id("Sandbox-Foobar.Sandbox.Localhost:8000", "sandbox.localhost") == "foobar"

    def test_hyphenated_name(self):
        assert extract_sandbox_id("sandbox-my-cool-box.treadstone-ai.dev", "treadstone-ai.dev") == "my-cool-box"

    def test_api_subdomain_ignored(self):
        assert extract_sandbox_id("api.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_www_subdomain_ignored(self):
        assert extract_sandbox_id("www.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_docs_subdomain_ignored(self):
        assert extract_sandbox_id("docs.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_demo_subdomain_ignored(self):
        assert extract_sandbox_id("demo.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_bare_prefix_no_name(self):
        assert extract_sandbox_id("sandbox-.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_no_match_exact_domain(self):
        assert extract_sandbox_id("treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_no_match_different_domain(self):
        assert extract_sandbox_id("sandbox-foo.other.dev", "treadstone-ai.dev") is None

    def test_no_match_nested_subdomain(self):
        assert extract_sandbox_id("a.sandbox-foo.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_custom_prefix(self):
        assert extract_sandbox_id("sb-test.sandbox.localhost:8000", "sandbox.localhost", prefix="sb-") == "test"

    def test_custom_prefix_no_match(self):
        assert extract_sandbox_id("sandbox-foo.treadstone-ai.dev", "treadstone-ai.dev", prefix="sb-") is None


class TestStripInternalAuth:
    def test_preserves_authorization_and_app_session_cookie(self):
        headers = {
            "authorization": "Bearer app-token",
            "cookie": "ts_bui=treadstone-cookie; session=app-session; csrftoken=abc123",
        }

        filtered = _strip_internal_auth(headers)

        assert filtered["authorization"] == "Bearer app-token"
        assert filtered["cookie"] == "session=app-session; csrftoken=abc123"

    def test_preserves_quoted_cookie_values(self):
        headers = {
            "cookie": 'prefs="a b"; ts_bui=treadstone-cookie; json="{\\"foo\\": \\"bar baz\\"}"',
        }

        filtered = _strip_internal_auth(headers)

        assert filtered["cookie"] == 'prefs="a b"; json="{\\"foo\\": \\"bar baz\\"}"'
