"""CLI browser-based authentication flow.

Endpoints for creating, polling, and exchanging CLI login flows,
plus redirect stubs that point browsers to the SPA login pages.
"""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Header, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.auth import authenticate_email_password
from treadstone.api.deps import optional_cookie_user
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import AuthRequiredError, BadRequestError, NotFoundError
from treadstone.core.request_context import set_request_context
from treadstone.core.users import get_jwt_strategy
from treadstone.models.cli_login_flow import (
    CLI_FLOW_TTL_SECONDS,
    CliLoginFlow,
    generate_flow_secret,
    hash_flow_secret,
)
from treadstone.models.user import User, utc_now
from treadstone.services.audit import record_audit_event

router = APIRouter(prefix="/v1/auth/cli", tags=["auth"])


async def _get_flow_or_404(session: AsyncSession, flow_id: str) -> CliLoginFlow:
    result = await session.execute(select(CliLoginFlow).where(CliLoginFlow.id == flow_id))
    flow = result.scalar_one_or_none()
    if flow is None:
        raise NotFoundError("CLI login flow", flow_id)
    return flow


def _verify_flow_secret(flow: CliLoginFlow, raw_secret: str | None) -> None:
    if not raw_secret:
        raise AuthRequiredError("Missing flow secret.")
    if hash_flow_secret(raw_secret) != flow.flow_secret_hash:
        raise AuthRequiredError("Invalid flow secret.")


def _effective_status(flow: CliLoginFlow) -> str:
    if flow.status == "pending":
        now = utc_now()
        expires = flow.gmt_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=now.tzinfo)
        if now > expires:
            return "expired"
    return flow.status


def _mark_approved(flow: CliLoginFlow, user: User, provider: str) -> None:
    flow.status = "approved"
    flow.user_id = user.id
    flow.provider = provider
    flow.gmt_completed = utc_now()


async def validate_cli_flow_secret(
    session: AsyncSession,
    flow_id: str,
    raw_secret: str | None,
) -> CliLoginFlow:
    flow = await _get_flow_or_404(session, flow_id)
    _verify_flow_secret(flow, raw_secret)
    return flow


@router.post("/flows")
async def create_cli_flow(session: AsyncSession = Depends(get_session)):
    """Create a CLI login flow for browser-based authentication."""
    raw_secret = generate_flow_secret()
    now = utc_now()
    flow = CliLoginFlow(
        flow_secret_hash=hash_flow_secret(raw_secret),
        status="pending",
        gmt_created=now,
        gmt_expires=now + timedelta(seconds=CLI_FLOW_TTL_SECONDS),
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)

    browser_url = (
        f"{settings.app_base_url.rstrip('/')}/auth/cli/login?"
        f"{urlencode({'flow_id': flow.id, 'flow_secret': raw_secret})}"
    )
    return {
        "flow_id": flow.id,
        "flow_secret": raw_secret,
        "browser_url": browser_url,
        "expires_at": flow.gmt_expires.isoformat(),
        "poll_interval": 2,
    }


@router.get("/flows/{flow_id}/status")
async def poll_cli_flow(
    flow_id: str,
    x_flow_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Poll the status of a CLI login flow."""
    flow = await _get_flow_or_404(session, flow_id)
    _verify_flow_secret(flow, x_flow_secret)
    return {"status": _effective_status(flow)}


@router.post("/flows/{flow_id}/exchange")
async def exchange_cli_flow(
    flow_id: str,
    x_flow_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Exchange an approved CLI login flow for a session token."""
    flow = await _get_flow_or_404(session, flow_id)
    _verify_flow_secret(flow, x_flow_secret)

    status = _effective_status(flow)
    if status == "expired":
        raise BadRequestError("CLI login flow has expired.")
    if status == "used":
        raise BadRequestError("CLI login flow has already been used.")
    if status != "approved":
        raise BadRequestError(f"CLI login flow is not approved (status: {status}).")

    user = await session.get(User, flow.user_id)
    if user is None:
        raise BadRequestError("User associated with this flow no longer exists.")

    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)

    flow.status = "used"
    session.add(flow)
    await session.commit()

    return {"session_token": token}


@router.get("/login", include_in_schema=False)
async def cli_login_page(
    flow_id: str = Query(...),
    flow_secret: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    """Redirect to the SPA CLI login page."""
    params: dict[str, str] = {"flow_id": flow_id}
    if flow_secret:
        params["flow_secret"] = flow_secret
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/auth/cli/login?{urlencode(params)}", status_code=303)


@router.post("/login", include_in_schema=False)
async def cli_login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    flow_id: str = Form(...),
    flow_secret: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Handle email/password login from the SPA CLI login page."""
    flow = await validate_cli_flow_secret(session, flow_id, flow_secret)
    status = _effective_status(flow)
    if status != "pending":
        raise BadRequestError("CLI login flow has already been used or has expired.")

    try:
        user = await authenticate_email_password(session, email, password)
    except BadRequestError:
        await record_audit_event(
            session,
            action="auth.login",
            target_type="user",
            result="failure",
            error_code="bad_request",
            metadata={"email": email, "surface": "cli"},
            request=request,
        )
        await session.commit()
        raise

    _mark_approved(flow, user, provider="email")
    set_request_context(request, actor_user_id=user.id, credential_type="cookie")
    await record_audit_event(
        session,
        action="auth.login",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "provider": "email", "surface": "cli"},
        request=request,
    )
    session.add(flow)
    await session.commit()

    return JSONResponse({"status": "approved"})


@router.post("/flows/{flow_id}/approve")
async def approve_cli_flow(
    request: Request,
    flow_id: str,
    x_flow_secret: str | None = Header(default=None),
    current_user: User = Depends(optional_cookie_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Approve a pending CLI login flow using the current browser session."""
    if current_user is None:
        raise AuthRequiredError("You must be signed in to approve a CLI login flow.")

    flow = await validate_cli_flow_secret(session, flow_id, x_flow_secret)
    status = _effective_status(flow)
    if status != "pending":
        raise BadRequestError("CLI login flow has already been used or has expired.")

    _mark_approved(flow, current_user, provider="session")
    set_request_context(request, actor_user_id=current_user.id, credential_type="cookie")
    await record_audit_event(
        session,
        action="auth.login",
        target_type="user",
        target_id=current_user.id,
        metadata={"email": current_user.email, "provider": "session", "surface": "cli"},
        request=request,
    )
    session.add(flow)
    await session.commit()

    return {"status": "approved"}
