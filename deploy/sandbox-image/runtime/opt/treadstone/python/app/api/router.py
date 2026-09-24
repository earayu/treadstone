from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, PlainTextResponse

from app.api.v1 import browser, file, sandbox, shell
from app.core.service_container import services


def register_routes(app: FastAPI) -> None:
    v1 = APIRouter(prefix="/v1")
    v1.include_router(sandbox.router, prefix="/sandbox", tags=["sandbox"])
    v1.include_router(shell.router, prefix="/shell", tags=["shell"])
    v1.include_router(file.router, prefix="/file", tags=["file"])
    v1.include_router(browser.router, prefix="/browser", tags=["browser"])
    app.include_router(v1)

    @app.get("/health", include_in_schema=False)
    async def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/terminal", include_in_schema=False)
    async def serve_terminal() -> FileResponse:
        return FileResponse("/opt/terminal/index.html", media_type="text/html")

    @app.get("/llms.txt", include_in_schema=False)
    async def serve_llms_txt() -> PlainTextResponse:
        service = services.get("sandbox_service")
        return PlainTextResponse(service.generate_llms_txt(app.openapi()))
