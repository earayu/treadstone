import os

from treadstone.config import Settings

DB_URL = "postgresql+asyncpg://x:y@host/db?sslmode=require"


def _clean_settings(**kwargs) -> Settings:
    """Create Settings isolated from env vars so unit tests check true defaults."""
    env_backup = {}
    prefix = "TREADSTONE_"
    for key in list(os.environ):
        if key.startswith(prefix):
            env_backup[key] = os.environ.pop(key)
    try:
        return Settings(_env_file=None, database_url=DB_URL, **kwargs)
    finally:
        os.environ.update(env_backup)


def test_settings_defaults():
    s = _clean_settings()
    assert s.app_name == "treadstone"
    assert s.debug is False


def test_settings_override():
    s = _clean_settings(app_name="test-app", debug=True)
    assert s.app_name == "test-app"
    assert s.debug is True


def test_auth_defaults():
    s = _clean_settings()
    assert s.auth_type == "cookie"
    assert s.register_mode == "unlimited"
    assert s.jwt_secret == "CHANGE_ME_IN_PROD"


def test_auth_type_override():
    s = _clean_settings(auth_type="logto")
    assert s.auth_type == "logto"


def test_oauth_defaults_empty():
    s = _clean_settings()
    assert s.google_oauth_client_id == ""
    assert s.github_oauth_client_secret == ""
