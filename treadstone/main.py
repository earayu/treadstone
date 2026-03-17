from fastapi import FastAPI

from treadstone.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health():
    return {"status": "ok"}
