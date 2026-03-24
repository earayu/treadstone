import pytest

from treadstone.config import Settings, validate_runtime_settings

DB_URL = "postgresql+asyncpg://x:y@host/db?sslmode=require"


def test_settings_defaults():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.app_name == "treadstone"
    assert s.debug is False


def test_settings_override():
    s = Settings(_env_file=None, app_name="test-app", debug=True, database_url=DB_URL)
    assert s.app_name == "test-app"
    assert s.debug is True


def test_auth_defaults():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.auth_type == "cookie"
    assert s.register_mode == "unlimited"
    assert s.jwt_secret == "CHANGE_ME_IN_PROD"


def test_auth_type_override():
    s = Settings(_env_file=None, database_url=DB_URL, auth_type="logto")
    assert s.auth_type == "logto"


def test_oauth_defaults_empty():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.google_oauth_client_id == ""
    assert s.github_oauth_client_secret == ""


def test_validate_runtime_settings_rejects_default_secret():
    s = Settings(_env_file=None, database_url=DB_URL)
    with pytest.raises(RuntimeError, match="TREADSTONE_JWT_SECRET"):
        validate_runtime_settings(s)


def test_validate_runtime_settings_rejects_short_secret():
    s = Settings(_env_file=None, database_url=DB_URL, jwt_secret="too-short-secret")
    with pytest.raises(RuntimeError, match="TREADSTONE_JWT_SECRET"):
        validate_runtime_settings(s)


def test_validate_runtime_settings_rejects_external_oidc():
    s = Settings(_env_file=None, database_url=DB_URL, jwt_secret="x" * 32, auth_type="logto")
    with pytest.raises(RuntimeError, match="not supported yet"):
        validate_runtime_settings(s)


def test_validate_runtime_settings_rejects_public_sandbox_domain():
    s = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="x" * 32,
        sandbox_domain="treadstone-ai.dev",
    )
    with pytest.raises(RuntimeError, match="Sandbox subdomain Web UI"):
        validate_runtime_settings(s)


def test_validate_runtime_settings_allows_local_sandbox_domain():
    s = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="x" * 32,
        sandbox_domain="sandbox.localhost",
    )
    validate_runtime_settings(s)
