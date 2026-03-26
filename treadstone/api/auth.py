from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from html import escape
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_users import exceptions as fastapi_users_exceptions
from fastapi_users.password import PasswordHelper
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from treadstone.api.deps import get_current_admin, get_current_control_plane_user, optional_cookie_user
from treadstone.api.schemas import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyScope,
    ApiKeySummary,
    ChangePasswordRequest,
    CreateApiKeyRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    UpdateApiKeyRequest,
    UserDetailResponse,
    UserListResponse,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import BadRequestError, ConflictError, NotFoundError, ValidationError
from treadstone.core.request_context import set_request_context
from treadstone.core.users import (
    COOKIE_MAX_AGE,
    UserManager,
    get_github_oauth_client,
    get_google_oauth_client,
    get_jwt_strategy,
    get_user_manager,
    should_use_secure_cookies,
)
from treadstone.models.api_key import (
    ApiKey,
    ApiKeySandboxGrant,
    build_api_key_preview,
    hash_api_key_secret,
)
from treadstone.models.sandbox import Sandbox
from treadstone.models.user import OAuthAccount, Role, User, random_id, utc_now
from treadstone.services.audit import record_audit_event
from treadstone.services.browser_login import validate_browser_return_to

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])

OAUTH_STATE_AUDIENCE = "treadstone:oauth-state"
OAUTH_STATE_TTL_SECONDS = 600


def _oauth_csrf_cookie_name(provider: str) -> str:
    return f"oauth_{provider}_csrf"


def _oauth_return_to_cookie_name(provider: str) -> str:
    return f"oauth_{provider}_return_to"


def _oauth_callback_url(provider: str) -> str:
    return f"{settings.api_base_url.rstrip('/')}/v1/auth/{provider}/callback"


def _oauth_state_payload(provider: str, csrf_token: str, return_to: str | None) -> str:
    payload: dict[str, str | int] = {
        "aud": OAUTH_STATE_AUDIENCE,
        "provider": provider,
        "csrf": csrf_token,
        "exp": int(utc_now().timestamp()) + OAUTH_STATE_TTL_SECONDS,
    }
    if return_to is not None:
        payload["return_to"] = return_to
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode_oauth_state(state: str) -> dict[str, str]:
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=OAUTH_STATE_AUDIENCE,
        )
    except jwt.PyJWTError as exc:
        raise BadRequestError("Invalid or expired OAuth state.") from exc
    return payload


def _set_oauth_flow_cookies(response: Response, provider: str, csrf_token: str, return_to: str | None) -> None:
    response.set_cookie(
        key=_oauth_csrf_cookie_name(provider),
        value=csrf_token,
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookies(),
    )
    if return_to is not None:
        response.set_cookie(
            key=_oauth_return_to_cookie_name(provider),
            value=return_to,
            max_age=OAUTH_STATE_TTL_SECONDS,
            httponly=True,
            samesite="lax",
            secure=should_use_secure_cookies(),
        )


def _clear_oauth_flow_cookies(response: Response, provider: str) -> None:
    response.delete_cookie(key=_oauth_csrf_cookie_name(provider))
    response.delete_cookie(key=_oauth_return_to_cookie_name(provider))


def _oauth_success_page(provider: str) -> HTMLResponse:
    title = escape(f"{provider.title()} login successful")
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
  <title>{title}</title>
</head>
<body style="{body_style}">
  <main style="{main_style}">
    <h1 style="font-size:24px;margin-bottom:12px;">Login successful</h1>
    <p style="color:#555;">You can close this window and return to Treadstone.</p>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html)


def _oauth_error_message(provider: str, error: str, error_description: str | None = None) -> str:
    if error == "access_denied":
        return f"{provider.title()} login was cancelled."
    if error_description:
        return error_description
    return f"{provider.title()} login failed."


def _oauth_login_redirect(return_to: str, message: str) -> RedirectResponse:
    return RedirectResponse(
        url=f"/v1/browser/login?{urlencode({'return_to': return_to, 'error': message})}",
        status_code=303,
    )


def _resolve_browser_return_to(
    request: Request,
    provider: str,
    state_payload: dict[str, str] | None = None,
) -> str | None:
    if state_payload is not None:
        return_to = state_payload.get("return_to")
        if return_to:
            validate_browser_return_to(return_to)
            return return_to

    cookie_return_to = request.cookies.get(_oauth_return_to_cookie_name(provider))
    if cookie_return_to:
        validate_browser_return_to(cookie_return_to)
        return cookie_return_to
    return None


def _get_oauth_client(provider: str):
    if provider == "google":
        oauth_client = get_google_oauth_client()
    elif provider == "github":
        oauth_client = get_github_oauth_client()
    else:
        oauth_client = None

    if oauth_client is None:
        raise BadRequestError(f"{provider.title()} OAuth is not configured.")
    return oauth_client


async def _get_github_verified_identity(oauth_client, access_token: str) -> tuple[str, str | None]:
    profile = await oauth_client.get_profile(access_token)
    emails = await oauth_client.get_emails(access_token)

    account_email = next(
        (
            str(email["email"])
            for email in emails
            if email.get("primary") and email.get("verified") and email.get("email")
        ),
        None,
    )
    if account_email is None:
        account_email = next(
            (str(email["email"]) for email in emails if email.get("verified") and email.get("email")),
            None,
        )

    return str(profile["id"]), account_email


async def _get_oauth_identity(provider: str, oauth_client, access_token: str) -> tuple[str, str | None]:
    if provider == "github":
        return await _get_github_verified_identity(oauth_client, access_token)
    return await oauth_client.get_id_email(access_token)


async def _record_oauth_success_events(
    *,
    session: AsyncSession,
    request: Request,
    user: User,
    provider: str,
    outcome: str,
    surface: str,
) -> None:
    if outcome == "register":
        await record_audit_event(
            session,
            action="auth.register",
            target_type="user",
            target_id=user.id,
            metadata={"email": user.email, "role": user.role, "provider": provider, "surface": surface},
            request=request,
        )
    elif outcome == "link":
        await record_audit_event(
            session,
            action="auth.oauth.link",
            target_type="user",
            target_id=user.id,
            metadata={"email": user.email, "provider": provider, "surface": surface},
            request=request,
        )

    await record_audit_event(
        session,
        action="auth.login",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "provider": provider, "oauth_action": outcome, "surface": surface},
        request=request,
    )


def _default_api_key_scope() -> ApiKeyScope:
    return ApiKeyScope()


async def authenticate_email_password(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.unique().scalar_one_or_none()

    if user is None or not user.is_active:
        raise BadRequestError("Invalid email or password")

    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(password, user.hashed_password)
    if not valid:
        raise BadRequestError("Invalid email or password")

    return user


async def write_session_cookie(response: Response, user: User) -> str:
    strategy = get_jwt_strategy()
    token = await strategy.write_token(user)
    response.set_cookie(
        key="session",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=should_use_secure_cookies(),
    )
    return token


async def _validate_owned_sandbox_ids(session: AsyncSession, owner_id: str, sandbox_ids: list[str]) -> list[str]:
    if not sandbox_ids:
        return []

    deduped = list(dict.fromkeys(sandbox_ids))
    result = await session.execute(
        select(Sandbox.id).where(
            Sandbox.owner_id == owner_id,
            Sandbox.id.in_(deduped),
        )
    )
    owned_ids = result.scalars().all()
    if set(owned_ids) != set(deduped):
        raise ValidationError("sandbox_ids must all belong to the current user.")
    return deduped


async def _resolve_api_key_scope(
    session: AsyncSession,
    owner_id: str,
    scope: ApiKeyScope | None,
) -> tuple[ApiKeyScope, list[str]]:
    resolved_scope = scope or _default_api_key_scope()
    sandbox_ids = await _validate_owned_sandbox_ids(session, owner_id, resolved_scope.data_plane.sandbox_ids)
    return resolved_scope, sandbox_ids


def _serialize_api_key_scope(api_key: ApiKey) -> dict:
    sandbox_ids = [grant.sandbox_id for grant in api_key.sandbox_grants]
    return _scope_payload_from_values(
        control_plane_enabled=api_key.control_plane_enabled,
        data_plane_mode=api_key.data_plane_mode,
        sandbox_ids=sandbox_ids,
    )


def _scope_payload_from_values(
    *,
    control_plane_enabled: bool,
    data_plane_mode: str,
    sandbox_ids: list[str],
) -> dict:
    return {
        "control_plane": control_plane_enabled,
        "data_plane": {"mode": data_plane_mode, "sandbox_ids": sandbox_ids},
    }


def _serialize_api_key_summary(api_key: ApiKey) -> dict:
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key_prefix": api_key.key_preview,
        "created_at": api_key.gmt_created,
        "updated_at": api_key.gmt_updated,
        "expires_at": api_key.gmt_expires,
        "scope": _serialize_api_key_scope(api_key),
    }


async def _replace_api_key_sandbox_grants(session: AsyncSession, api_key: ApiKey, sandbox_ids: list[str]) -> None:
    await session.execute(delete(ApiKeySandboxGrant).where(ApiKeySandboxGrant.api_key_id == api_key.id))
    for sandbox_id in sandbox_ids:
        session.add(ApiKeySandboxGrant(api_key_id=api_key.id, sandbox_id=sandbox_id))


async def _load_api_key_with_grants(session: AsyncSession, key_id: str) -> ApiKey:
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.id == key_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with email + password, set session cookie."""
    try:
        user = await authenticate_email_password(session, str(body.email), body.password)
    except BadRequestError:
        await record_audit_event(
            session,
            action="auth.login",
            target_type="user",
            result="failure",
            error_code="bad_request",
            metadata={"email": str(body.email), "surface": "api"},
            request=request,
        )
        await session.commit()
        raise

    set_request_context(request, actor_user_id=user.id, credential_type="cookie")

    response = Response(
        content='{"detail":"Login successful"}',
        media_type="application/json",
    )
    await write_session_cookie(response, user)
    await record_audit_event(
        session,
        action="auth.login",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "surface": "api"},
        request=request,
    )
    await session.commit()
    return response


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    current_user: User | None = Depends(optional_cookie_user),
    session: AsyncSession = Depends(get_session),
):
    """Clear the session cookie."""
    if current_user is not None:
        set_request_context(request, actor_user_id=current_user.id, credential_type="cookie")
        await record_audit_event(
            session,
            action="auth.logout",
            target_type="user",
            target_id=current_user.id,
            request=request,
        )
        await session.commit()

    response = Response(
        content='{"detail":"Logout successful"}',
        media_type="application/json",
    )
    response.delete_cookie(key="session")
    return response


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
async def register(
    request: Request,
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    count_result = await session.execute(select(func.count()).select_from(User))
    user_count = count_result.scalar_one()
    is_first_user = user_count == 0

    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.unique().scalar_one_or_none():
        raise ConflictError("Email already registered")

    ph = PasswordHelper()
    hashed = ph.hash(body.password)

    role = Role.ADMIN if is_first_user else Role.RO
    user = User(
        email=body.email,
        hashed_password=hashed,
        is_active=True,
        is_superuser=(role == Role.ADMIN),
        is_verified=True,
        role=role.value,
    )
    session.add(user)
    await session.flush()

    set_request_context(request, actor_user_id=user.id)
    await record_audit_event(
        session,
        action="auth.register",
        target_type="user",
        target_id=user.id,
        metadata={"email": user.email, "role": user.role},
        request=request,
    )
    await session.commit()

    await session.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role}


async def _oauth_authorize(provider: str, return_to: str | None) -> RedirectResponse:
    oauth_client = _get_oauth_client(provider)
    if return_to is not None:
        validate_browser_return_to(return_to)

    csrf_token = secrets.token_urlsafe(32)
    state = _oauth_state_payload(provider, csrf_token, return_to)
    authorization_url = await oauth_client.get_authorization_url(_oauth_callback_url(provider), state)
    response = RedirectResponse(url=authorization_url, status_code=303)
    _set_oauth_flow_cookies(response, provider, csrf_token, return_to)
    return response


async def _oauth_callback(
    provider: str,
    request: Request,
    user_manager: UserManager,
    session: AsyncSession,
    code: str | None,
    state: str | None,
    error: str | None,
    error_description: str | None,
):
    oauth_client = _get_oauth_client(provider)
    state_payload: dict[str, str] | None = None

    if state is not None:
        try:
            state_payload = _decode_oauth_state(state)
        except BadRequestError:
            return_to = _resolve_browser_return_to(request, provider)
            if return_to is not None:
                response = _oauth_login_redirect(return_to, "Your login session expired. Please try again.")
                _clear_oauth_flow_cookies(response, provider)
                return response
            raise
        if state_payload.get("provider") != provider:
            raise BadRequestError("Invalid OAuth state.")

    return_to = _resolve_browser_return_to(request, provider, state_payload)
    surface = "browser" if return_to is not None else "api"

    if error is not None:
        message = _oauth_error_message(provider, error, error_description)
        set_request_context(request, error_code=error)
        if return_to is not None:
            response = _oauth_login_redirect(return_to, message)
            _clear_oauth_flow_cookies(response, provider)
            return response
        raise BadRequestError(message)

    if code is None or state_payload is None:
        raise BadRequestError("Missing OAuth code or state.")

    cookie_csrf_token = request.cookies.get(_oauth_csrf_cookie_name(provider))
    state_csrf_token = state_payload.get("csrf")
    if not cookie_csrf_token or not state_csrf_token or not secrets.compare_digest(cookie_csrf_token, state_csrf_token):
        set_request_context(request, error_code="oauth_invalid_state")
        if return_to is not None:
            response = _oauth_login_redirect(return_to, "Your login session expired. Please try again.")
            _clear_oauth_flow_cookies(response, provider)
            return response
        raise BadRequestError("Invalid OAuth state.")

    try:
        token = await oauth_client.get_access_token(code, _oauth_callback_url(provider))
        account_id, account_email = await _get_oauth_identity(provider, oauth_client, token["access_token"])
    except Exception as exc:
        logger.exception(
            "OAuth %s token exchange or profile fetch failed",
            provider,
        )
        set_request_context(request, error_code="oauth_provider_error")
        message = f"{provider.title()} login failed."
        if return_to is not None:
            response = _oauth_login_redirect(return_to, message)
            _clear_oauth_flow_cookies(response, provider)
            return response
        raise BadRequestError(message) from exc

    if account_email is None:
        error_code = "oauth_missing_verified_email" if provider == "github" else "oauth_missing_email"
        set_request_context(request, error_code=error_code)
        if provider == "github":
            message = "GitHub did not provide a verified email address."
        else:
            message = f"{provider.title()} did not provide an email address."
        if return_to is not None:
            response = _oauth_login_redirect(return_to, message)
            _clear_oauth_flow_cookies(response, provider)
            return response
        raise BadRequestError(message)

    existing_oauth = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.oauth_name == provider,
            OAuthAccount.account_id == account_id,
        )
    )
    existing_account = existing_oauth.scalar_one_or_none()
    if existing_account is not None:
        outcome = "login"
    else:
        existing_user = await session.execute(select(User).where(User.email == account_email))
        outcome = "link" if existing_user.unique().scalar_one_or_none() is not None else "register"

    try:
        user = await user_manager.oauth_callback(
            provider,
            token["access_token"],
            account_id,
            account_email,
            token.get("expires_at"),
            token.get("refresh_token"),
            request,
            associate_by_email=True,
            is_verified_by_default=True,
        )
    except fastapi_users_exceptions.UserAlreadyExists as exc:
        raise ConflictError("Email already registered") from exc

    set_request_context(request, actor_user_id=user.id, credential_type="cookie")
    await _record_oauth_success_events(
        session=session,
        request=request,
        user=user,
        provider=provider,
        outcome=outcome,
        surface=surface,
    )
    await session.commit()

    if return_to is not None:
        response: Response = RedirectResponse(
            url=f"/v1/browser/bootstrap?{urlencode({'return_to': return_to})}",
            status_code=303,
        )
    else:
        response = _oauth_success_page(provider)
    await write_session_cookie(response, user)
    _clear_oauth_flow_cookies(response, provider)
    return response


@router.get("/google/authorize", include_in_schema=False)
async def google_authorize(return_to: str | None = Query(default=None)):
    return await _oauth_authorize("google", return_to)


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    request: Request,
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    return await _oauth_callback("google", request, user_manager, session, code, state, error, error_description)


@router.get("/github/authorize", include_in_schema=False)
async def github_authorize(return_to: str | None = Query(default=None)):
    return await _oauth_authorize("github", return_to)


@router.get("/github/callback", include_in_schema=False)
async def github_callback(
    request: Request,
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    return await _oauth_callback("github", request, user_manager, session, code, state, error, error_description)


@router.get("/user", response_model=UserDetailResponse)
async def get_user(current_user: User = Depends(get_current_control_plane_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


@router.get("/users", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of items to return."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
):
    if current_user.role == Role.ADMIN.value:
        result = await session.execute(select(User))
        users = list(result.unique().scalars().all())
    else:
        users = [current_user]
    total = len(users)
    page = users[offset : offset + limit]
    return {"items": [{"id": u.id, "email": u.email, "role": u.role} for u in page], "total": total}


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    ph = PasswordHelper()
    valid, _ = ph.verify_and_update(body.old_password, current_user.hashed_password)
    if not valid:
        raise BadRequestError("Wrong current password")
    user = await session.get(User, current_user.id)
    if not user:
        raise NotFoundError("User", current_user.id)
    user.hashed_password = ph.hash(body.new_password)
    session.add(user)
    await record_audit_event(
        session,
        action="auth.password.change",
        target_type="user",
        target_id=user.id,
        request=request,
    )
    await session.commit()
    return {"detail": "Password changed"}


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == current_user.id:
        raise BadRequestError("Cannot delete yourself")
    target = await session.get(User, user_id)
    if not target:
        raise NotFoundError("User", user_id)
    if target.role == Role.ADMIN.value:
        admin_count_result = await session.execute(
            select(func.count()).select_from(User).where(User.role == Role.ADMIN.value)
        )
        if admin_count_result.scalar_one() <= 1:
            raise BadRequestError("Cannot delete the last admin")
    metadata = {"email": target.email, "role": target.role}
    await session.delete(target)
    await record_audit_event(
        session,
        action="auth.user.delete",
        target_type="user",
        target_id=user_id,
        metadata=metadata,
        request=request,
    )
    await session.commit()


@router.post("/api-keys", status_code=status.HTTP_201_CREATED, response_model=ApiKeyResponse)
async def create_api_key(
    request: Request,
    body: CreateApiKeyRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    key_value = "sk-" + secrets.token_hex(24)
    gmt_expires = None
    if body.expires_in is not None:
        gmt_expires = utc_now() + timedelta(seconds=body.expires_in)
    resolved_scope, sandbox_ids = await _resolve_api_key_scope(session, current_user.id, body.scope)
    scope_metadata = _scope_payload_from_values(
        control_plane_enabled=resolved_scope.control_plane,
        data_plane_mode=resolved_scope.data_plane.mode.value,
        sandbox_ids=sandbox_ids,
    )
    api_key = ApiKey(
        id="key" + random_id(),
        key_hash=hash_api_key_secret(key_value),
        key_preview=build_api_key_preview(key_value),
        name=body.name,
        user_id=current_user.id,
        control_plane_enabled=resolved_scope.control_plane,
        data_plane_mode=resolved_scope.data_plane.mode.value,
        gmt_expires=gmt_expires,
    )
    session.add(api_key)
    await session.flush()
    await _replace_api_key_sandbox_grants(session, api_key, sandbox_ids)
    await record_audit_event(
        session,
        action="auth.api_key.create",
        target_type="api_key",
        target_id=api_key.id,
        metadata={"name": api_key.name, "scope": scope_metadata},
        request=request,
    )
    await session.commit()
    api_key = await _load_api_key_with_grants(session, api_key.id)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": key_value,
        "created_at": api_key.gmt_created,
        "updated_at": api_key.gmt_updated,
        "expires_at": api_key.gmt_expires,
        "scope": _serialize_api_key_scope(api_key),
    }


@router.get("/api-keys", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    keys = result.scalars().all()
    return {"items": [_serialize_api_key_summary(k) for k in keys]}


@router.patch("/api-keys/{key_id}", response_model=ApiKeySummary)
async def update_api_key(
    request: Request,
    key_id: str,
    body: UpdateApiKeyRequest,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    scope_metadata: dict | None = None
    result = await session.execute(
        select(ApiKey)
        .options(selectinload(ApiKey.sandbox_grants))
        .where(ApiKey.id == key_id, ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key", key_id)

    if body.name is not None:
        api_key.name = body.name

    if body.expires_in is not None:
        api_key.gmt_expires = utc_now() + timedelta(seconds=body.expires_in)
    elif body.clear_expiration:
        api_key.gmt_expires = None

    if body.scope is not None:
        resolved_scope, sandbox_ids = await _resolve_api_key_scope(session, current_user.id, body.scope)
        api_key.control_plane_enabled = resolved_scope.control_plane
        api_key.data_plane_mode = resolved_scope.data_plane.mode.value
        await _replace_api_key_sandbox_grants(session, api_key, sandbox_ids)
        scope_metadata = _scope_payload_from_values(
            control_plane_enabled=resolved_scope.control_plane,
            data_plane_mode=resolved_scope.data_plane.mode.value,
            sandbox_ids=sandbox_ids,
        )

    api_key.gmt_updated = utc_now()
    session.add(api_key)
    await record_audit_event(
        session,
        action="auth.api_key.update",
        target_type="api_key",
        target_id=api_key.id,
        metadata={"name": api_key.name, "scope": scope_metadata or _serialize_api_key_scope(api_key)},
        request=request,
    )
    await session.commit()
    api_key = await _load_api_key_with_grants(session, api_key.id)
    return _serialize_api_key_summary(api_key)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    request: Request,
    key_id: str,
    current_user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current_user.id, ApiKey.gmt_deleted.is_(None))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key", key_id)
    api_key.gmt_deleted = utc_now()
    api_key.gmt_updated = utc_now()
    session.add(api_key)
    await record_audit_event(
        session,
        action="auth.api_key.delete",
        target_type="api_key",
        target_id=api_key.id,
        metadata={"name": api_key.name},
        request=request,
    )
    await session.commit()
