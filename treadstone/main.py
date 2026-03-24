import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError

from treadstone.api.auth import router as auth_router
from treadstone.api.config import router as config_router
from treadstone.api.sandbox_proxy import router as sandbox_proxy_router
from treadstone.api.sandbox_templates import router as sandbox_templates_router
from treadstone.api.sandboxes import router as sandboxes_router
from treadstone.api.schemas import HealthResponse
from treadstone.config import settings, validate_runtime_settings
from treadstone.core.errors import TreadstoneError
from treadstone.core.users import auth_backend, fastapi_users, github_oauth_client, google_oauth_client
from treadstone.middleware.sandbox_subdomain import SandboxSubdomainMiddleware
from treadstone.services.sandbox_proxy import close_http_client

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


@asynccontextmanager
async def lifespan(app: FastAPI):
    from treadstone.core.database import async_session
    from treadstone.services.k8s_client import get_k8s_client
    from treadstone.services.k8s_sync import start_sync_loop
    from treadstone.services.leader_election import K8sLeaseStore, LeaderElector
    from treadstone.services.sync_supervisor import LeaderControlledSyncSupervisor

    if settings.leader_election_enabled:
        holder_identity = settings.pod_name or os.getenv("HOSTNAME") or "treadstone-api"
        lease_namespace = settings.pod_namespace or settings.sandbox_namespace
        elector = LeaderElector(
            lease_store=K8sLeaseStore(),
            namespace=lease_namespace,
            lease_name=settings.leader_election_lease_name,
            holder_identity=holder_identity,
            lease_duration_seconds=settings.leader_election_lease_duration_seconds,
            renew_interval_seconds=settings.leader_election_renew_interval_seconds,
            retry_interval_seconds=settings.leader_election_retry_interval_seconds,
        )
        supervisor = LeaderControlledSyncSupervisor(
            elector=elector,
            sync_loop_factory=lambda: start_sync_loop(settings.sandbox_namespace, get_k8s_client(), async_session),
        )
        logger.info(
            "Leader election enabled for K8s sync loop (lease=%s, namespace=%s, holder=%s)",
            settings.leader_election_lease_name,
            lease_namespace,
            holder_identity,
        )
        sync_task = asyncio.create_task(supervisor.run())
        try:
            yield
        finally:
            await supervisor.shutdown()
            sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await sync_task
            await close_http_client()
        return

    logger.info("Leader election disabled; starting K8s sync loop directly")
    sync_task = asyncio.create_task(start_sync_loop(settings.sandbox_namespace, get_k8s_client(), async_session))
    try:
        yield
    finally:
        sync_task.cancel()
        with suppress(asyncio.CancelledError):
            await sync_task
        await close_http_client()


logging.basicConfig(level=logging.DEBUG if settings.debug else logging.WARNING)

validate_runtime_settings(settings)

app = FastAPI(
    title=settings.app_name,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    servers=[
        {"url": "https://api.treadstone-ai.dev", "description": "Production"},
        {"url": "https://demo.treadstone-ai.dev", "description": "Demo"},
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
)


@app.exception_handler(TreadstoneError)
async def treadstone_error_handler(request: Request, exc: TreadstoneError):
    return JSONResponse(status_code=exc.status, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = exc.errors()
    messages = []
    for err in details:
        loc = " -> ".join(str(part) for part in err.get("loc", []))
        messages.append(f"{loc}: {err.get('msg', 'invalid')}")
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "; ".join(messages), "status": 422}},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    logger.error("Unhandled IntegrityError: %s", exc)
    body = {
        "error": {
            "code": "conflict",
            "message": "Resource already exists or constraint violated.",
            "status": 409,
        }
    }
    return JSONResponse(status_code=409, content=body)


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    body = {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "status": 500,
        }
    }
    return JSONResponse(status_code=500, content=body)


# ── Middleware (outermost = first to run) ──
app.add_middleware(SandboxSubdomainMiddleware)

# ── Routes ──
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(sandbox_proxy_router)
app.include_router(sandbox_templates_router)
app.include_router(sandboxes_router)

if google_oauth_client:
    app.include_router(
        fastapi_users.get_oauth_router(google_oauth_client, auth_backend, settings.jwt_secret),
        prefix="/v1/auth/google",
        tags=["auth"],
    )

if github_oauth_client:
    app.include_router(
        fastapi_users.get_oauth_router(github_oauth_client, auth_backend, settings.jwt_secret),
        prefix="/v1/auth/github",
        tags=["auth"],
    )


@app.get("/health", tags=["system"], response_model=HealthResponse)
async def health():
    return {"status": "ok"}
