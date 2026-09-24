import pytest
from sqlalchemy import text

import treadstone.core.database as db_mod


@pytest.mark.integration
async def test_postgres_connection_and_version() -> None:
    """Verify connectivity using the database selected by the integration fixture."""
    async with db_mod.engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

        result = await conn.execute(text("SELECT version()"))
        version = result.scalar()
        assert "PostgreSQL" in version
