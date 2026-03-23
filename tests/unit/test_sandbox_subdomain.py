"""Unit tests for sandbox subdomain extraction (prefix-based)."""

from treadstone.middleware.sandbox_subdomain import extract_sandbox_name


class TestExtractSandboxName:
    """extract_sandbox_name recognises the ``sandbox-`` prefix and strips it."""

    def test_valid_sandbox_subdomain(self):
        assert extract_sandbox_name("sandbox-foobar.treadstone-ai.dev", "treadstone-ai.dev") == "foobar"

    def test_valid_with_port(self):
        assert extract_sandbox_name("sandbox-foobar.sandbox.localhost:8000", "sandbox.localhost") == "foobar"

    def test_case_insensitive(self):
        assert extract_sandbox_name("Sandbox-Foobar.Sandbox.Localhost:8000", "sandbox.localhost") == "foobar"

    def test_hyphenated_name(self):
        assert extract_sandbox_name("sandbox-my-cool-box.treadstone-ai.dev", "treadstone-ai.dev") == "my-cool-box"

    def test_api_subdomain_ignored(self):
        assert extract_sandbox_name("api.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_www_subdomain_ignored(self):
        assert extract_sandbox_name("www.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_docs_subdomain_ignored(self):
        assert extract_sandbox_name("docs.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_demo_subdomain_ignored(self):
        assert extract_sandbox_name("demo.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_bare_prefix_no_name(self):
        assert extract_sandbox_name("sandbox-.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_no_match_exact_domain(self):
        assert extract_sandbox_name("treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_no_match_different_domain(self):
        assert extract_sandbox_name("sandbox-foo.other.dev", "treadstone-ai.dev") is None

    def test_no_match_nested_subdomain(self):
        assert extract_sandbox_name("a.sandbox-foo.treadstone-ai.dev", "treadstone-ai.dev") is None

    def test_custom_prefix(self):
        assert extract_sandbox_name("sb-test.sandbox.localhost:8000", "sandbox.localhost", prefix="sb-") == "test"

    def test_custom_prefix_no_match(self):
        assert extract_sandbox_name("sandbox-foo.treadstone-ai.dev", "treadstone-ai.dev", prefix="sb-") is None
