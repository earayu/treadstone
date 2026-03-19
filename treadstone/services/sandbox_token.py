"""Sandbox Token service — issue and verify JWTs scoped to a single sandbox."""

from datetime import UTC, datetime, timedelta

import jwt

from treadstone.config import settings

_ALGORITHM = "HS256"
_DEFAULT_EXPIRES_IN = 3600  # 1 hour


def create_sandbox_token(
    sandbox_id: str,
    user_id: str,
    expires_in: int = _DEFAULT_EXPIRES_IN,
) -> tuple[str, datetime]:
    exp = datetime.now(UTC) + timedelta(seconds=expires_in)
    payload = {
        "sandbox_id": sandbox_id,
        "user_id": user_id,
        "exp": exp,
        "type": "sandbox_token",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)
    return token, exp


def verify_sandbox_token(token: str) -> dict:
    """Verify and decode a sandbox token.

    Returns {"sandbox_id": ..., "user_id": ...} on success.
    Raises jwt.InvalidTokenError on failure.
    """
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "sandbox_token":
        raise jwt.InvalidTokenError("Not a sandbox token")
    return {"sandbox_id": payload["sandbox_id"], "user_id": payload["user_id"]}
