import ssl

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from treadstone.config import settings


@pytest.mark.integration
async def test_neon_connection_and_version():
    """验证能连接到真实的 Neon 数据库并获取版本"""
    url = settings.database_url
    connect_args: dict = {}
    if "sslmode=require" in url:
        url = url.replace("?sslmode=require", "").replace("&sslmode=require", "")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    engine = create_async_engine(url, connect_args=connect_args)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            assert "PostgreSQL" in version
    finally:
        await engine.dispose()
