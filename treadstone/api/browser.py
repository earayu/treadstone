from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import optional_cookie_user
from treadstone.core.database import get_session
from treadstone.core.errors import NotFoundError
from treadstone.core.request_context import set_request_context
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import User
from treadstone.services.browser_auth import issue_bootstrap_ticket
from treadstone.services.browser_login import validate_browser_return_to

router = APIRouter(prefix="/v1/browser", tags=["browser"])


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
            url=f"/auth/sign-in?{urlencode({'return_to': return_to})}",
            status_code=303,
        )
    set_request_context(request, actor_user_id=current_user.id, credential_type="cookie")

    result = await session.execute(
        select(Sandbox).where(
            Sandbox.id == sandbox_id,
            Sandbox.owner_id == current_user.id,
            Sandbox.gmt_deleted.is_(None),
        )
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        raise NotFoundError("Sandbox", sandbox_id)

    ticket = issue_bootstrap_ticket(sandbox_id=sandbox.id, next_path=next_path)
    redirect_to = f"{scheme}://{host}/_treadstone/open?{urlencode({'ticket': ticket, 'next': next_path})}"
    return RedirectResponse(url=redirect_to, status_code=303)


@router.get("/login", include_in_schema=False)
async def browser_login_page(return_to: str = Query(...), error: str | None = Query(default=None)):
    """Redirect to the SPA sign-in page with return_to preserved."""
    params: dict[str, str] = {"return_to": return_to}
    if error:
        params["error"] = error
    return RedirectResponse(url=f"/auth/sign-in?{urlencode(params)}", status_code=303)
