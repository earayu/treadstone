from pathlib import Path

import pytest

import treadstone.core.database as db_mod

ENV_TEST_PATH = Path(__file__).parent / ".env.test"


def _load_test_db_url() -> str | None:
    """Load DATABASE_URL from .env.test if it exists."""
    if not ENV_TEST_PATH.exists():
        return None
    for line in ENV_TEST_PATH.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() == "TREADSTONE_DATABASE_URL":
            return val.strip()
    return None


@pytest.fixture(autouse=True)
async def reset_engine_for_integration():
    """Dispose and rebuild the global engine for each test.

    If tests/integration/.env.test exists and contains TREADSTONE_DATABASE_URL,
    that URL is used (typically a Neon test branch). Otherwise falls back to
    the default settings.database_url.
    """
    await db_mod.engine.dispose()
    test_url = _load_test_db_url()
    db_mod.engine = db_mod._build_engine(url=test_url)
    db_mod.async_session = db_mod.async_sessionmaker(db_mod.engine, class_=db_mod.AsyncSession, expire_on_commit=False)
    yield
    await db_mod.engine.dispose()
