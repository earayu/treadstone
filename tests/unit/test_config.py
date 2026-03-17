from treadstone.config import Settings


def test_settings_defaults():
    s = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://x:y@host/db?sslmode=require",
    )
    assert s.app_name == "treadstone"
    assert s.debug is False


def test_settings_override():
    s = Settings(
        _env_file=None,
        app_name="test-app",
        debug=True,
        database_url="postgresql+asyncpg://x:y@host/db?sslmode=require",
    )
    assert s.app_name == "test-app"
    assert s.debug is True
