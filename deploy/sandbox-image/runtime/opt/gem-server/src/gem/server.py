import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .routers import auth, cdp, gui, ping


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Context manager for application lifespan events.
    Handles startup and shutdown tasks.
    """
    # Startup
    logging.info("Application starting up...")
    await auth.startup(app)
    await cdp.startup(app)

    yield

    # Shutdown
    logging.info("Application shutting down...")
    await cdp.shutdown(app)


api = FastAPI(
    title="Environment Service",
    description="API for controlling environment and proxying CDP.",
    version="0.1.1",
    lifespan=lifespan,
    redirect_slashes=False,
)

api.include_router(auth.router)
api.include_router(cdp.router)
api.include_router(gui.router)
api.include_router(ping.router)
