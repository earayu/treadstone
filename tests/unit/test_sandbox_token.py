"""Unit tests for sandbox token service."""

import time

import jwt
import pytest

from treadstone.services.sandbox_token import create_sandbox_token, verify_sandbox_token


def test_create_returns_jwt_string():
    token, exp = create_sandbox_token("sb-123", "user-456")
    assert isinstance(token, str)
    assert len(token) > 20
    assert exp is not None


def test_verify_valid_token():
    token, _ = create_sandbox_token("sb-abc", "user-xyz")
    result = verify_sandbox_token(token)
    assert result["sandbox_id"] == "sb-abc"
    assert result["user_id"] == "user-xyz"


def test_verify_expired_token():
    token, _ = create_sandbox_token("sb-abc", "user-xyz", expires_in=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_sandbox_token(token)


def test_verify_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        verify_sandbox_token("not-a-real-token")


def test_verify_wrong_type_raises():
    from treadstone.config import settings

    payload = {"sandbox_id": "sb-1", "user_id": "u-1", "type": "other", "exp": time.time() + 3600}
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError, match="Not a sandbox token"):
        verify_sandbox_token(token)
