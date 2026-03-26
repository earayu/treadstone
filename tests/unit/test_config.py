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


def test_settings_api_base_url_default():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.api_base_url == "http://localhost"


def test_auth_defaults():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.auth_type == "cookie"
    assert s.jwt_secret == "CHANGE_ME_IN_PROD"


def test_sandbox_storage_defaults():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.sandbox_storage_class == "treadstone-workspace"
    assert s.sandbox_default_storage_size == "5Gi"


def test_auth_type_override():
    s = Settings(_env_file=None, database_url=DB_URL, auth_type="logto")
    assert s.auth_type == "logto"


def test_oauth_defaults_empty():
    s = Settings(_env_file=None, database_url=DB_URL)
    assert s.google_oauth_client_id == ""
    assert s.github_oauth_client_secret == ""


def test_settings_ignore_removed_oauth_and_invitation_env_vars(monkeypatch):
    monkeypatch.setenv("TREADSTONE_REGISTER_MODE", "unlimited")
    monkeypatch.setenv("TREADSTONE_OAUTH_REDIRECT_URL", "http://localhost:3000/auth/callback")

    s = Settings(_env_file=None, database_url=DB_URL)

    assert s.auth_type == "cookie"


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


def test_validate_runtime_settings_allows_public_sandbox_domain():
    s = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="x" * 32,
        sandbox_domain="treadstone-ai.dev",
        api_base_url="https://api.treadstone-ai.dev",
    )
    validate_runtime_settings(s)


def test_validate_runtime_settings_rejects_public_sandbox_domain_with_local_api_base_url():
    s = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="x" * 32,
        sandbox_domain="treadstone-ai.dev",
        api_base_url="http://localhost:8000",
    )
    with pytest.raises(RuntimeError, match="TREADSTONE_API_BASE_URL"):
        validate_runtime_settings(s)


def test_validate_runtime_settings_allows_local_sandbox_domain():
    s = Settings(
        _env_file=None,
        database_url=DB_URL,
        jwt_secret="x" * 32,
        sandbox_domain="sandbox.localhost",
    )
    validate_runtime_settings(s)
