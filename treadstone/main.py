from fastapi import Depends, FastAPI
from sqlalchemy import text

from treadstone.api.auth import router as auth_router
from treadstone.api.deps import get_current_user
from treadstone.config import settings
from treadstone.core.database import engine
from treadstone.core.users import auth_backend, fastapi_users, github_oauth_client, google_oauth_client
from treadstone.models.user import User

app = FastAPI(title=settings.app_name)

# ── Auth routes ──
app.include_router(auth_router)

if google_oauth_client:
    app.include_router(
        fastapi_users.get_oauth_router(google_oauth_client, auth_backend, settings.jwt_secret),
        prefix="/api/auth/google",
        tags=["auth"],
    )

if github_oauth_client:
    app.include_router(
        fastapi_users.get_oauth_router(github_oauth_client, auth_backend, settings.jwt_secret),
        prefix="/api/auth/github",
        tags=["auth"],
    )


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
