from __future__ import annotations

from html import escape
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
from treadstone.core.users import get_github_oauth_client, get_google_oauth_client
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User
from treadstone.services.audit import record_audit_event
from treadstone.services.browser_auth import issue_bootstrap_ticket
from treadstone.services.browser_login import validate_browser_return_to

router = APIRouter(prefix="/v1/browser", tags=["browser"])


def _render_login_page(return_to: str, error: str | None = None, status_code: int = 200) -> HTMLResponse:
    error_html = ""
    if error:
        error_html = f'<p style="color:#b91c1c;margin-bottom:16px;">{escape(error)}</p>'
    oauth_buttons: list[str] = []
    if get_google_oauth_client():
        google_href = f"/v1/auth/google/authorize?{urlencode({'return_to': return_to})}"
        oauth_buttons.append(
            '<a href="'
            f"{escape(google_href, quote=True)}"
            '" style="display:block;text-align:center;margin-bottom:12px;padding:10px 12px;'
            'border:1px solid #d4d4d8;border-radius:8px;color:#111827;font-weight:600;text-decoration:none;">'
            "Continue with Google"
            "</a>"
        )
    if get_github_oauth_client():
        github_href = f"/v1/auth/github/authorize?{urlencode({'return_to': return_to})}"
        oauth_buttons.append(
            '<a href="'
            f"{escape(github_href, quote=True)}"
            '" style="display:block;text-align:center;margin-bottom:12px;padding:10px 12px;'
            'border:1px solid #d4d4d8;border-radius:8px;color:#111827;font-weight:600;text-decoration:none;">'
            "Continue with GitHub"
            "</a>"
        )
    oauth_html = "".join(oauth_buttons)
    divider_html = ""
    if oauth_buttons:
        divider_html = (
            '<p style="margin:20px 0;color:#71717a;text-align:center;font-size:14px;">or continue with email</p>'
        )
    body_style = (
        "font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;padding:40px;"
    )
    main_style = (
        "max-width:420px;margin:0 auto;background:white;padding:24px;"
        "border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.08);"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Treadstone Login</title>
</head>
<body style="{body_style}">
  <main style="{main_style}">
    <h1 style="font-size:24px;margin-bottom:12px;">Sign in to open your sandbox</h1>
    <p style="color:#555;margin-bottom:20px;">Use your Treadstone account to continue.</p>
    {error_html}
    {oauth_html}
    {divider_html}
    <form method="post" action="/v1/browser/login">
      <input type="hidden" name="return_to" value="{escape(return_to, quote=True)}">
      <label style="display:block;margin-bottom:12px;">
        <span style="display:block;margin-bottom:6px;">Email</span>
        <input
          type="email"
          name="email"
          required
          style="width:100%;padding:10px 12px;border:1px solid #d4d4d8;border-radius:8px;"
        >
      </label>
      <label style="display:block;margin-bottom:20px;">
        <span style="display:block;margin-bottom:6px;">Password</span>
        <input
          type="password"
          name="password"
          required
          style="width:100%;padding:10px 12px;border:1px solid #d4d4d8;border-radius:8px;"
        >
      </label>
      <button
        type="submit"
        style="width:100%;padding:10px 12px;border:0;border-radius:8px;background:#111827;color:white;font-weight:600;"
      >
        Sign in
      </button>
    </form>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status_code)


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
