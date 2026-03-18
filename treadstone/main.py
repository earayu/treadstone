from fastapi import Depends, FastAPI
from sqlalchemy import text

from treadstone.api.deps import get_current_user
from treadstone.config import settings
from treadstone.core.database import engine
from treadstone.models.user import User

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


@app.get("/api/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}
