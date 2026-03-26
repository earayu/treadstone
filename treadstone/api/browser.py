from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.auth import authenticate_email_password, write_session_cookie
from treadstone.api.deps import optional_cookie_user
from treadstone.core.database import get_session
from treadstone.core.errors import BadRequestError, NotFoundError
from treadstone.core.request_context import set_request_context
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User
from treadstone.services.audit import record_audit_event
from treadstone.services.browser_auth import issue_bootstrap_ticket
from treadstone.services.browser_login import validate_browser_return_to
from treadstone.services.login_page import render_login_page

router = APIRouter(prefix="/v1/browser", tags=["browser"])


def _render_login_page(return_to: str, error: str | None = None, status_code: int = 200) -> HTMLResponse:
    return render_login_page(
        title="Sign in to open your sandbox",
        subtitle="Use your Treadstone account to continue.",
        form_action="/v1/browser/login",
        hidden_fields={"return_to": return_to},
        google_authorize_params={"return_to": return_to},
        github_authorize_params={"return_to": return_to},
        error=error,
        status_code=status_code,
    )


@router.get("/bootstrap", include_in_schema=False)
async def browser_bootstrap(
    request: Request,
    return_to: str = Query(...),
    current_user: User | None = Depends(optional_cookie_user),
    session: AsyncSession = Depends(get_session),
):
    scheme, host, sandbox_id, next_path = validate_browser_return_to(return_to)
    set_request_context(request, sandbox_id=sandbox_id)

    if current_user is None:
        return RedirectResponse(
            url=f"/v1/browser/login?{urlencode({'return_to': return_to})}",
            status_code=303,
        )
    set_request_context(request, actor_user_id=current_user.id, credential_type="cookie")

    result = await session.execute(
        select(Sandbox).where(
            Sandbox.id == sandbox_id,
            Sandbox.owner_id == current_user.id,
        )
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise NotFoundError("Sandbox", sandbox_id)

    ticket = issue_bootstrap_ticket(sandbox_id=sandbox.id, next_path=next_path)
    redirect_to = f"{scheme}://{host}/_treadstone/open?{urlencode({'ticket': ticket, 'next': next_path})}"
    return RedirectResponse(url=redirect_to, status_code=303)


@router.get("/login", include_in_schema=False)
async def browser_login_page(request: Request, return_to: str = Query(...), error: str | None = Query(default=None)):
    _, _, sandbox_id, _ = validate_browser_return_to(return_to)
    set_request_context(request, sandbox_id=sandbox_id)
    return _render_login_page(return_to, error=error)


@router.post("/login", include_in_schema=False)
async def browser_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    return_to: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    _, _, sandbox_id, _ = validate_browser_return_to(return_to)
    set_request_context(request, sandbox_id=sandbox_id)
    try:
        user = await authenticate_email_password(session, email, password)
    except BadRequestError:
        await record_audit_event(
            session,
            action="auth.login",
            target_type="user",
            result="failure",
            error_code="bad_request",
            metadata={"email": email, "surface": "browser"},
            request=request,
        )
        await session.commit()
        return _render_login_page(return_to, error="Invalid email or password.", status_code=400)

    set_request_context(request, actor_user_id=user.id, credential_type="cookie")
    await record_audit_event(
        session,
        action="auth.login",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "surface": "browser"},
        request=request,
    )
    await session.commit()
    response = RedirectResponse(url=f"/v1/browser/bootstrap?{urlencode({'return_to': return_to})}", status_code=303)
    await write_session_cookie(response, user)
    return response
