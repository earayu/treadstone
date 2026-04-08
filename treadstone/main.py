import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError

from treadstone.api.admin import router as admin_router
from treadstone.api.audit import router as audit_router
from treadstone.api.auth import router as auth_router
from treadstone.api.browser import router as browser_router
from treadstone.api.cli_auth import router as cli_auth_router
from treadstone.api.config import router as config_router
from treadstone.api.docs import router as docs_router
from treadstone.api.sandbox_proxy import router as sandbox_proxy_router
from treadstone.api.sandbox_templates import router as sandbox_templates_router
from treadstone.api.sandboxes import router as sandboxes_router
from treadstone.api.schemas import HealthResponse
from treadstone.api.support import router as support_router
from treadstone.api.usage import router as usage_router
from treadstone.api.waitlist import router as waitlist_router
from treadstone.config import settings, validate_runtime_settings
from treadstone.core.errors import TreadstoneError
from treadstone.middleware.request_logging import RequestLoggingMiddleware
from treadstone.middleware.sandbox_subdomain import SandboxSubdomainMiddleware
from treadstone.openapi_spec import build_full_openapi_spec, filter_public_openapi, merge_sandbox_paths
from treadstone.services.sandbox_proxy import close_http_client

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


async def _run_metering_loop(session_factory) -> None:
    """Run the periodic metering tick loop for single-process deployments."""
    from treadstone.services.metering_tasks import TICK_INTERVAL, run_metering_tick
    from treadstone.services.sync_supervisor import _k8s_stop_sandbox

    while True:
        try:
            await run_metering_tick(session_factory, stop_sandbox_callback=_k8s_stop_sandbox)
        except Exception:
            logger.exception("Metering tick failed")
        await asyncio.sleep(TICK_INTERVAL)


async def _run_lifecycle_loop(session_factory) -> None:
    """Run the periodic lifecycle tick loop for single-process deployments."""
    from treadstone.services.sandbox_lifecycle_tasks import LIFECYCLE_TICK_INTERVAL, run_lifecycle_tick
    from treadstone.services.sync_supervisor import _k8s_delete_sandbox, _k8s_stop_sandbox

    while True:
        try:
            await run_lifecycle_tick(
                session_factory,
                stop_sandbox_callback=_k8s_stop_sandbox,
                delete_sandbox_callback=_k8s_delete_sandbox,
            )
        except Exception:
            logger.exception("Lifecycle tick failed")
        await asyncio.sleep(LIFECYCLE_TICK_INTERVAL)


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
            session_factory=async_session,
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
    metering_task = asyncio.create_task(_run_metering_loop(async_session))
    lifecycle_task = asyncio.create_task(_run_lifecycle_loop(async_session))
    try:
        yield
    finally:
        sync_task.cancel()
        metering_task.cancel()
        lifecycle_task.cancel()
        with suppress(asyncio.CancelledError):
            await sync_task
        with suppress(asyncio.CancelledError):
            await metering_task
        with suppress(asyncio.CancelledError):
            await lifecycle_task
        await close_http_client()


logging.basicConfig(level=logging.DEBUG if settings.debug else logging.WARNING)
# Keep third-party noise low (root WARNING) while still emitting INFO from our package.
_treadstone_log = logging.getLogger("treadstone")
_treadstone_log.setLevel(logging.DEBUG if settings.debug else logging.INFO)

validate_runtime_settings(settings)

app = FastAPI(
    title=settings.app_name,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
    servers=[{"url": "https://api.treadstone-ai.dev", "description": "Production"}],
)


@app.exception_handler(TreadstoneError)
async def treadstone_error_handler(request: Request, exc: TreadstoneError):
    request.state.error_code = exc.code
    return JSONResponse(status_code=exc.status, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request.state.error_code = "validation_error"
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
    request.state.error_code = "conflict"
    logger.exception("Unhandled IntegrityError: %s", exc)
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
    request.state.error_code = "internal_error"
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SandboxSubdomainMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# ── Routes ──
app.include_router(docs_router)
app.include_router(admin_router)
app.include_router(audit_router)
app.include_router(auth_router)
app.include_router(browser_router)
app.include_router(cli_auth_router)
app.include_router(config_router)
app.include_router(sandbox_proxy_router)
app.include_router(sandbox_templates_router)
app.include_router(sandboxes_router)
app.include_router(support_router)
app.include_router(usage_router)
app.include_router(waitlist_router)


@app.get("/health", tags=["system"], response_model=HealthResponse)
async def health():
    return {"status": "ok"}


def _public_openapi() -> dict[str, Any]:
    """Serve OpenAPI for Swagger UI: public control-plane paths + sandbox runtime proxy paths.

    Admin and audit paths are excluded (matching the public SDK).  Sandbox internal
    paths are merged in so the docs show how to reach sandbox operations through the
    ``/v1/sandboxes/{sandbox_id}/proxy/...`` endpoint.

    NOTE: ``export_openapi.py`` does NOT call ``merge_sandbox_paths``, so the Python
    SDK (generated from ``openapi-public.json``) is unaffected.
    """
    if app.openapi_schema is not None:
        return app.openapi_schema
    full = build_full_openapi_spec(app)
    public = filter_public_openapi(full)
    app.openapi_schema = merge_sandbox_paths(public)
    return app.openapi_schema


app.openapi = _public_openapi  # type: ignore[method-assign]
