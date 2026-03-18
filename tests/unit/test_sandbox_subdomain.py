"""Unit tests for sandbox subdomain extraction."""

from treadstone.middleware.sandbox_subdomain import extract_sandbox_id


class TestExtractSandboxId:
    def test_valid_subdomain(self):
        assert extract_sandbox_id("sb-123.sandbox.localhost:8000", "sandbox.localhost") == "sb-123"

    def test_valid_subdomain_no_port(self):
        assert extract_sandbox_id("sb-123.sandbox.example.com", "sandbox.example.com") == "sb-123"

    def test_case_insensitive(self):
        assert extract_sandbox_id("SB-123.Sandbox.Localhost:8000", "sandbox.localhost") == "sb-123"

    def test_no_match_different_domain(self):
        assert extract_sandbox_id("sb-123.other.localhost:8000", "sandbox.localhost") is None

    def test_no_match_exact_domain(self):
        assert extract_sandbox_id("sandbox.localhost:8000", "sandbox.localhost") is None

    def test_no_match_nested_subdomain(self):
        assert extract_sandbox_id("a.b.sandbox.localhost:8000", "sandbox.localhost") is None

    def test_no_match_regular_host(self):
        assert extract_sandbox_id("localhost:8000", "sandbox.localhost") is None

    def test_hyphenated_sandbox_id(self):
        assert (
            extract_sandbox_id("sandbox-claim-test-01.sandbox.localhost:8000", "sandbox.localhost")
            == "sandbox-claim-test-01"
        )
