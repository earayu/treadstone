from __future__ import annotations

from html import escape
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.auth import authenticate_email_password, write_session_cookie
from treadstone.api.deps import optional_cookie_user
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import BadRequestError, NotFoundError, ValidationError
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User
from treadstone.services.browser_auth import issue_bootstrap_ticket

router = APIRouter(prefix="/v1/browser", tags=["browser"])


def _extract_sandbox_name(host: str) -> str | None:
    host_no_port = host.split(":")[0].lower()
    domain = settings.sandbox_domain.lower()

    if not host_no_port.endswith(f".{domain}"):
        return None

    subdomain = host_no_port[: -(len(domain) + 1)]
    if not subdomain or "." in subdomain:
        return None
    if not subdomain.startswith(settings.sandbox_subdomain_prefix):
        return None
    name = subdomain[len(settings.sandbox_subdomain_prefix) :]
    return name if name else None


def _validate_return_to(return_to: str) -> tuple[str, str, str, str]:
    parsed = urlparse(return_to)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("return_to must be an absolute sandbox Web UI URL.")

    sandbox_name = _extract_sandbox_name(parsed.netloc)
    if sandbox_name is None:
        raise ValidationError("return_to must target a sandbox subdomain.")

    next_path = parsed.path or "/"
    if parsed.query:
        next_path = f"{next_path}?{parsed.query}"

    return parsed.scheme, parsed.netloc, sandbox_name, next_path


def _render_login_page(return_to: str, error: str | None = None, status_code: int = 200) -> HTMLResponse:
    error_html = ""
    if error:
        error_html = f'<p style="color:#b91c1c;margin-bottom:16px;">{escape(error)}</p>'
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
    return_to: str = Query(...),
    current_user: User | None = Depends(optional_cookie_user),
    session: AsyncSession = Depends(get_session),
):
    scheme, host, sandbox_name, next_path = _validate_return_to(return_to)

    if current_user is None:
        return RedirectResponse(
            url=f"/v1/browser/login?{urlencode({'return_to': return_to})}",
            status_code=303,
        )

    result = await session.execute(
        select(Sandbox).where(
            Sandbox.name == sandbox_name,
            Sandbox.owner_id == current_user.id,
            Sandbox.gmt_deleted.is_(None),
        )
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise NotFoundError("Sandbox", sandbox_name)

    ticket = issue_bootstrap_ticket(sandbox_id=sandbox.id, next_path=next_path)
    redirect_to = f"{scheme}://{host}/_treadstone/open?{urlencode({'ticket': ticket, 'next': next_path})}"
    return RedirectResponse(url=redirect_to, status_code=303)


@router.get("/login", include_in_schema=False)
async def browser_login_page(return_to: str = Query(...)):
    return _render_login_page(return_to)


@router.post("/login", include_in_schema=False)
async def browser_login(
    email: str = Form(...),
    password: str = Form(...),
    return_to: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        user = await authenticate_email_password(session, email, password)
    except BadRequestError:
        return _render_login_page(return_to, error="Invalid email or password.", status_code=400)

    response = RedirectResponse(url=f"/v1/browser/bootstrap?{urlencode({'return_to': return_to})}", status_code=303)
    await write_session_cookie(response, user)
    return response
