"""Admin API — composite router assembling domain-specific admin sub-routers.

All URL paths are preserved: each sub-router defines unprefixed routes,
and this top-level router applies the ``/v1/admin`` prefix uniformly.
"""

from fastapi import APIRouter

from treadstone.identity.api.admin_users import router as users_router
from treadstone.metering.api.admin_metering import router as metering_router
from treadstone.platform.api.admin_platform import router as platform_router
from treadstone.sandbox.api.admin_sandbox import router as sandbox_router

router = APIRouter(prefix="/v1/admin", tags=["admin"])
router.include_router(users_router)
router.include_router(metering_router)
router.include_router(platform_router)
router.include_router(sandbox_router)
