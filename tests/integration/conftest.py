import pytest

import treadstone.core.database as db_mod


@pytest.fixture(autouse=True)
async def reset_engine_for_integration():
    """Dispose and rebuild the global engine so it binds to the current test's event loop."""
    await db_mod.engine.dispose()
    db_mod.engine = db_mod._build_engine()
    db_mod.async_session = db_mod.async_sessionmaker(db_mod.engine, class_=db_mod.AsyncSession, expire_on_commit=False)
    yield
    await db_mod.engine.dispose()
