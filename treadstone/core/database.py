import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from treadstone.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine(url: str | None = None):
    connect_args: dict = {}
    db_url = url or settings.database_url
    if "sslmode=require" in db_url:
        db_url = db_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx
    return create_async_engine(db_url, echo=settings.debug, connect_args=connect_args)


engine = _build_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
