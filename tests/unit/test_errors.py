"""Unit tests for unified error format."""

from treadstone.core.errors import (
    AuthRequiredError,
    ForbiddenError,
    SandboxNotFoundError,
    SandboxNotReadyError,
    SandboxUnreachableError,
    TreadstoneError,
)


def test_treadstone_error_to_dict():
    err = TreadstoneError(code="test_error", message="Something went wrong", status=500)
    d = err.to_dict()
    assert d == {"error": {"code": "test_error", "message": "Something went wrong", "status": 500}}


def test_auth_required_error():
    err = AuthRequiredError()
    assert err.code == "auth_required"
    assert err.status == 401


def test_forbidden_error():
    err = ForbiddenError()
    assert err.code == "forbidden"
    assert err.status == 403


def test_sandbox_not_found_error():
    err = SandboxNotFoundError("sb-123")
    d = err.to_dict()
    assert d["error"]["code"] == "sandbox_not_found"
    assert d["error"]["status"] == 404
    assert "sb-123" in d["error"]["message"]


def test_sandbox_not_ready_error():
    err = SandboxNotReadyError("sb-456", "stopped")
    d = err.to_dict()
    assert d["error"]["code"] == "sandbox_not_ready"
    assert d["error"]["status"] == 409
    assert "stopped" in d["error"]["message"]


def test_sandbox_unreachable_error():
    err = SandboxUnreachableError("sb-789")
    assert err.status == 502
    assert err.code == "sandbox_unreachable"
