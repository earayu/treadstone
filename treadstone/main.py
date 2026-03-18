from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from sqlalchemy import text

from treadstone.api.auth import router as auth_router
from treadstone.api.config import router as config_router
from treadstone.api.deps import get_current_user
from treadstone.config import settings
from treadstone.core.database import engine
from treadstone.core.users import auth_backend, fastapi_users, github_oauth_client, google_oauth_client
from treadstone.models.user import User


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


app = FastAPI(title=settings.app_name, generate_unique_id_function=custom_generate_unique_id)

# ── Routes ──
app.include_router(auth_router)
app.include_router(config_router)

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


@app.get("/health", tags=["system"])
async def health():
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db": db_ok}


@app.get("/api/me", tags=["auth"])
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}
