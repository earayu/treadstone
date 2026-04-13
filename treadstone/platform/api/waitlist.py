"""Waitlist API — public endpoint for submitting Pro/Ultra plan applications.

Endpoints:
  POST /v1/waitlist  — submit a waitlist application (no auth required)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.schemas import WaitlistApplicationRequest, WaitlistApplicationResponse
from treadstone.audit.services.audit import record_audit_event
from treadstone.core.database import get_session
from treadstone.core.errors import TreadstoneError
from treadstone.platform.models.waitlist import ApplicationStatus, WaitlistApplication
from treadstone.platform.services.platform_limits import PlatformLimitsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/waitlist", tags=["waitlist"])
_platform_limits = PlatformLimitsService()


def _serialize_application(app: WaitlistApplication) -> dict:
    return {
        "id": app.id,
        "email": app.email,
        "name": app.name,
        "target_tier": app.target_tier,
        "company": app.company,
        "github_or_portfolio_url": app.github_or_portfolio_url,
        "use_case": app.use_case,
        "status": app.status,
        "processed_at": app.processed_at,
        "gmt_created": app.gmt_created,
    }


@router.post("", status_code=201, response_model=WaitlistApplicationResponse)
async def submit_waitlist_application(
    request: Request,
    body: WaitlistApplicationRequest,
    session: AsyncSession = Depends(get_session),
) -> WaitlistApplicationResponse:
    """Submit a waitlist application for Pro or Ultra plan access.

    No authentication required — users may apply before registering. Multiple
    applications from the same email (including same tier) are allowed.
    """
    runtime = request.app.state.platform_limits_runtime
    snapshot = await runtime.ensure_snapshot(session)
    try:
        _platform_limits.check_waitlist_submission_allowed(snapshot)
    except TreadstoneError as exc:
        await record_audit_event(
            session,
            action="waitlist.submit",
            target_type="waitlist_application",
            result="failure",
            error_code=getattr(exc, "code", None),
            metadata={"email": body.email.lower(), "target_tier": body.target_tier},
            request=request,
        )
        await session.commit()
        raise

    email_lower = body.email.lower()

    application = WaitlistApplication(
        email=email_lower,
        name=body.name,
        target_tier=body.target_tier,
        company=body.company,
        github_or_portfolio_url=body.github_or_portfolio_url,
        use_case=body.use_case,
        status=ApplicationStatus.PENDING,
    )
    session.add(application)
    await session.commit()

    logger.info(
        "Waitlist application submitted: email=%s tier=%s id=%s",
        email_lower,
        body.target_tier,
        application.id,
    )
    return _serialize_application(application)
