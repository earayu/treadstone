from fastapi import FastAPI
from sqlalchemy import text

from treadstone.config import settings
from treadstone.core.database import engine

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db": db_ok}
