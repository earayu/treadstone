"""Sandbox CRUD API router — control plane endpoints."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_control_plane_user
from treadstone.api.schemas import (
    CreateSandboxRequest,
    SandboxDetailResponse,
    SandboxListResponse,
    SandboxResponse,
    SandboxWebLinkResponse,
    SandboxWebLinkStatusResponse,
    UpdateSandboxRequest,
)
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.errors import (
    ConflictError,
    EmailVerificationRequiredError,
    SandboxNotFoundError,
    TreadstoneError,
    ValidationError,
)
from treadstone.core.public_base_url import public_control_plane_base_url
from treadstone.core.request_context import set_request_context
from treadstone.models.sandbox import Sandbox, SandboxStatus
from treadstone.models.sandbox_web_link import SandboxWebLink
from treadstone.models.user import User, utc_now
from treadstone.services.audit import record_audit_event
from treadstone.services.browser_auth import build_open_link_token, build_open_link_url
from treadstone.services.metering_service import MeteringService
from treadstone.services.platform_limits import PlatformLimitsService
from treadstone.services.sandbox_service import SandboxService

router = APIRouter(prefix="/v1/sandboxes", tags=["sandboxes"])

_metering = MeteringService()
_platform_limits = PlatformLimitsService()


def _web_port_suffix(api_base: str) -> str:
    """Port to mirror on *.sandbox_domain web URLs, or empty if not needed.

    When the API is reached on a non-default port (e.g. dev :8000, kubectl
    port-forward), the browser-facing subdomain URL must use the same port.
    When the URL uses the default port or omits it (e.g. local Ingress on
    80/443), no suffix is added.
    """
    parsed = urlparse(str(api_base).rstrip("/"))
    port = parsed.port
    if port is None:
        return ""
    if parsed.scheme == "http" and port == 80:
        return ""
    if parsed.scheme == "https" and port == 443:
        return ""
    return f":{port}"


def _build_canonical_web_url(sb, base_url: str) -> str | None:
    if not settings.sandbox_domain:
        return None

    base = str(base_url).rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme in ("http", "https"):
        scheme = parsed.scheme
    else:
        scheme = "https" if base.startswith("https") else "http"
    return f"{scheme}://{settings.sandbox_subdomain_prefix}{sb.id}.{settings.sandbox_domain}{_web_port_suffix(base)}"


def _build_urls(sb, base_url: str, web_link: SandboxWebLink | None = None) -> dict:
    base = str(base_url).rstrip("/")
    proxy = f"{base}/v1/sandboxes/{sb.id}/proxy"
    mcp = f"{proxy}/mcp"
    web = _build_canonical_web_url(sb, base_url)
    if web is not None and web_link is not None and not web_link.is_expired() and web_link.gmt_deleted is None:
        web = build_open_link_url(web, web_link.id)
    return {"proxy": proxy, "mcp": mcp, "web": web}


def _to_response(sb, base_url: str, web_link: SandboxWebLink | None = None) -> dict:
    return {
        "id": sb.id,
        "name": sb.name,
        "template": sb.template,
        "status": sb.status,
        "labels": sb.labels or {},
        "auto_stop_interval": sb.auto_stop_interval,
        "auto_delete_interval": sb.auto_delete_interval,
        "persist": sb.persist,
        "storage_size": sb.storage_size,
        "pending_operation": sb.pending_operation,
        "storage": (
            {
                "mode": sb.storage_backend_mode or "live_disk",
                "size": sb.storage_size,
                "snapshot_created_at": sb.gmt_snapshotted,
                "zone": sb.workspace_zone,
            }
            if sb.persist and sb.storage_size
            else None
        ),
        "urls": _build_urls(sb, base_url, web_link),
        "created_at": sb.gmt_created,
    }


def _to_detail(sb, base_url: str, web_link: SandboxWebLink | None = None) -> dict:
    data = _to_response(sb, base_url, web_link)
    data.update(
        {
            "image": sb.image,
            "status_message": sb.status_message,
            "started_at": sb.gmt_started,
            "stopped_at": sb.gmt_stopped,
        }
    )
    return data


def _get_web_url(sb, base_url: str) -> str:
    web_url = _build_canonical_web_url(sb, base_url)
    if web_url is None:
        raise ValidationError("sandbox_domain must be configured to use sandbox Web UI links.")
    return web_url


def _get_platform_limits_runtime(request: Request):
    return request.app.state.platform_limits_runtime


async def _load_active_web_link(session: AsyncSession, sandbox_id: str) -> SandboxWebLink | None:
    result = await session.execute(
        select(SandboxWebLink).where(SandboxWebLink.sandbox_id == sandbox_id, SandboxWebLink.gmt_deleted.is_(None))
    )
    return _normalize_active_web_link(result.scalar_one_or_none())


def _normalize_active_web_link(link: SandboxWebLink | None) -> SandboxWebLink | None:
    if link is None or link.gmt_deleted is not None or link.is_expired():
        return None
    return link


async def _get_owned_sandbox_with_web_link_row(
    session: AsyncSession,
    sandbox_id: str,
    owner_id: str,
) -> tuple[Sandbox | None, SandboxWebLink | None]:
    result = await session.execute(
        select(Sandbox, SandboxWebLink)
        .outerjoin(
            SandboxWebLink,
            and_(
                SandboxWebLink.sandbox_id == Sandbox.id,
                SandboxWebLink.gmt_deleted.is_(None),
            ),
        )
        .where(
            Sandbox.id == sandbox_id,
            Sandbox.owner_id == owner_id,
            Sandbox.gmt_deleted.is_(None),
        )
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    return row


async def _get_owned_sandbox_with_active_web_link(
    session: AsyncSession,
    sandbox_id: str,
    owner_id: str,
) -> tuple[Sandbox | None, SandboxWebLink | None]:
    sandbox, link = await _get_owned_sandbox_with_web_link_row(session, sandbox_id, owner_id)
    return sandbox, _normalize_active_web_link(link)


async def _load_active_web_links(session: AsyncSession, sandbox_ids: list[str]) -> dict[str, SandboxWebLink]:
    if not sandbox_ids:
        return {}

    result = await session.execute(
        select(SandboxWebLink).where(
            SandboxWebLink.sandbox_id.in_(sandbox_ids),
            SandboxWebLink.gmt_deleted.is_(None),
        )
    )
    links = result.scalars().all()
    return {link.sandbox_id: link for link in links if not link.is_expired()}


async def _upsert_web_link(
    session: AsyncSession,
    sandbox,
    user_id: str,
    *,
    existing_link: SandboxWebLink | None = None,
) -> SandboxWebLink:
    link = existing_link
    if link is None:
        result = await session.execute(select(SandboxWebLink).where(SandboxWebLink.sandbox_id == sandbox.id))
        link = result.scalar_one_or_none()
    link_id = build_open_link_token()

    if link is None:
        link = SandboxWebLink(
            id=link_id,
            sandbox_id=sandbox.id,
            created_by_user_id=user_id,
            gmt_expires=None,
        )
    else:
        link.id = link_id
        link.created_by_user_id = user_id
        link.gmt_expires = None
        link.gmt_last_used = None
        link.gmt_updated = utc_now()
        link.gmt_deleted = None

    session.add(link)
    return link


async def _ensure_active_web_link(
    session: AsyncSession,
    sandbox,
    user_id: str,
) -> SandboxWebLink:
    _, existing_link = await _get_owned_sandbox_with_web_link_row(session, sandbox.id, sandbox.owner_id)
    link = _normalize_active_web_link(existing_link)
    if link is not None:
        return link
    return await _upsert_web_link(session, sandbox, user_id, existing_link=existing_link)


def _parse_label_filters(labels: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in labels:
        if ":" not in item:
            raise ValidationError("Each label filter must use key:value format.")
        key, value = item.split(":", 1)
        if not key or not value:
            raise ValidationError("Each label filter must use key:value format.")
        parsed[key] = value
    return parsed


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=SandboxResponse)
async def create_sandbox(
    request: Request,
    body: CreateSandboxRequest,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    if not user.is_verified:
        await record_audit_event(
            session,
            action="sandbox.create",
            target_type="sandbox",
            result="failure",
            error_code="email_verification_required",
            metadata={"email": user.email, "template": body.template},
            request=request,
        )
        await session.commit()
        raise EmailVerificationRequiredError()

    runtime = _get_platform_limits_runtime(request)
    snapshot = await runtime.ensure_snapshot(session)
    try:
        _platform_limits.check_sandbox_creation_allowed(snapshot)
        if body.persist:
            requested_storage_gib = _platform_limits.parse_storage_size_gib(
                body.storage_size or settings.sandbox_default_storage_size
            )
            _platform_limits.check_storage_allocation_allowed(snapshot, requested_storage_gib)
        else:
            requested_storage_gib = 0
    except TreadstoneError as exc:
        await record_audit_event(
            session,
            action="sandbox.create",
            target_type="sandbox",
            result="failure",
            error_code=getattr(exc, "code", None),
            metadata={
                "template": body.template,
                "persist": body.persist,
                "storage_size": (body.storage_size or settings.sandbox_default_storage_size) if body.persist else None,
            },
            request=request,
        )
        await session.commit()
        raise

    service = SandboxService(session=session, metering=_metering)
    sandbox = await service.create(
        owner_id=user.id,
        template=body.template,
        name=body.name,
        labels=body.labels,
        auto_stop_interval=body.auto_stop_interval,
        auto_delete_interval=body.auto_delete_interval,
        persist=body.persist,
        storage_size=body.storage_size or settings.sandbox_default_storage_size,
    )
    set_request_context(request, sandbox_id=sandbox.id)
    web_link = None
    if settings.sandbox_domain:
        web_link = await _upsert_web_link(session, sandbox, user.id)
        await record_audit_event(
            session,
            action="sandbox.web_link.create",
            target_type="sandbox",
            target_id=sandbox.id,
            metadata={"issued_via": "open_link", "auto_created": True},
            request=request,
        )
    await record_audit_event(
        session,
        action="sandbox.create",
        target_type="sandbox",
        target_id=sandbox.id,
        metadata={
            "name": sandbox.name,
            "template": sandbox.template,
            "persist": sandbox.persist,
            "storage_size": sandbox.storage_size,
        },
        request=request,
    )
    await session.commit()
    return _to_response(sandbox, public_control_plane_base_url(request), web_link)


@router.get("", response_model=SandboxListResponse)
async def list_sandboxes(
    request: Request,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
    label: list[str] = Query(default=[]),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of items to return."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
):
    labels_dict = _parse_label_filters(label)

    service = SandboxService(session=session)
    sandboxes, total = await service.list_by_owner(
        owner_id=user.id,
        labels=labels_dict or None,
        offset=offset,
        limit=limit,
    )
    page = sandboxes
    base_url = public_control_plane_base_url(request)
    web_links = await _load_active_web_links(session, [sb.id for sb in page]) if settings.sandbox_domain else {}
    return {"items": [_to_response(sb, base_url, web_links.get(sb.id)) for sb in page], "total": total}


@router.get("/{sandbox_id}", response_model=SandboxDetailResponse)
async def get_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    """Return DB-backed sandbox detail. K8s state is synced by Watch/reconcile only (no read-path K8s API calls)."""
    sandbox, web_link = await _get_owned_sandbox_with_active_web_link(session, sandbox_id, user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)
    set_request_context(request, sandbox_id=sandbox.id)
    return _to_detail(sandbox, public_control_plane_base_url(request), web_link)


@router.patch("/{sandbox_id}", response_model=SandboxDetailResponse)
async def update_sandbox(
    request: Request,
    sandbox_id: str,
    body: UpdateSandboxRequest,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise ValidationError("At least one field is required to update the sandbox.")
    service = SandboxService(session=session, metering=_metering)
    sandbox = await service.update(sandbox_id=sandbox_id, owner_id=user.id, patch=patch)
    set_request_context(request, sandbox_id=sandbox.id)
    await record_audit_event(
        session,
        action="sandbox.update",
        target_type="sandbox",
        target_id=sandbox.id,
        metadata={"fields": sorted(patch.keys())},
        request=request,
    )
    await session.commit()
    web_link = await _load_active_web_link(session, sandbox.id) if settings.sandbox_domain else None
    return _to_detail(sandbox, public_control_plane_base_url(request), web_link)


@router.delete("/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session, metering=_metering)
    sandbox = await service.delete(sandbox_id=sandbox_id, owner_id=user.id)
    if sandbox.status == SandboxStatus.ERROR:
        raise ConflictError(sandbox.status_message or f"Failed to delete sandbox {sandbox_id}.")
    set_request_context(request, sandbox_id=sandbox_id)
    if sandbox.storage_backend_mode == "standard_snapshot":
        await record_audit_event(
            session,
            action="sandbox.storage.asset_delete",
            target_type="sandbox",
            target_id=sandbox_id,
            metadata={"asset_type": "bound_snapshot"},
            request=request,
        )
    await record_audit_event(
        session,
        action="sandbox.delete",
        target_type="sandbox",
        target_id=sandbox_id,
        request=request,
    )
    await session.commit()


@router.post("/{sandbox_id}/snapshot", status_code=status.HTTP_202_ACCEPTED, response_model=SandboxDetailResponse)
async def snapshot_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session, metering=_metering)
    sandbox = await service.snapshot(sandbox_id=sandbox_id, owner_id=user.id)
    set_request_context(request, sandbox_id=sandbox.id)
    await record_audit_event(
        session,
        action="sandbox.snapshot",
        target_type="sandbox",
        target_id=sandbox.id,
        request=request,
    )
    await session.commit()
    web_link = await _load_active_web_link(session, sandbox.id) if settings.sandbox_domain else None
    return _to_detail(sandbox, public_control_plane_base_url(request), web_link)


@router.post("/{sandbox_id}/start", response_model=SandboxDetailResponse)
async def start_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session, metering=_metering)
    before = await service.get(sandbox_id=sandbox_id, owner_id=user.id)
    sandbox = await service.start(sandbox_id=sandbox_id, owner_id=user.id)
    set_request_context(request, sandbox_id=sandbox.id)
    if before is not None and before.status == "cold":
        await record_audit_event(
            session,
            action="sandbox.restore_on_start",
            target_type="sandbox",
            target_id=sandbox.id,
            request=request,
        )
    await record_audit_event(
        session,
        action="sandbox.start",
        target_type="sandbox",
        target_id=sandbox.id,
        request=request,
    )
    await session.commit()
    web_link = await _load_active_web_link(session, sandbox.id) if settings.sandbox_domain else None
    return _to_detail(sandbox, public_control_plane_base_url(request), web_link)


@router.post("/{sandbox_id}/stop", response_model=SandboxDetailResponse)
async def stop_sandbox(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    service = SandboxService(session=session, metering=_metering)
    sandbox = await service.stop(sandbox_id=sandbox_id, owner_id=user.id)
    set_request_context(request, sandbox_id=sandbox.id)
    await record_audit_event(
        session,
        action="sandbox.stop",
        target_type="sandbox",
        target_id=sandbox.id,
        request=request,
    )
    await session.commit()
    web_link = await _load_active_web_link(session, sandbox.id) if settings.sandbox_domain else None
    return _to_detail(sandbox, public_control_plane_base_url(request), web_link)


@router.post("/{sandbox_id}/web-link", response_model=SandboxWebLinkResponse)
async def create_sandbox_web_link(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    sandbox, existing_link = await _get_owned_sandbox_with_web_link_row(session, sandbox_id, user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)
    set_request_context(request, sandbox_id=sandbox.id)

    web_url = _get_web_url(sandbox, public_control_plane_base_url(request))
    link = _normalize_active_web_link(existing_link)
    if link is None:
        link = await _upsert_web_link(session, sandbox, user.id, existing_link=existing_link)
        await record_audit_event(
            session,
            action="sandbox.web_link.create",
            target_type="sandbox",
            target_id=sandbox.id,
            metadata={"issued_via": "open_link", "auto_created": False},
            request=request,
        )
        await session.commit()
    return {
        "web_url": web_url,
        "open_link": build_open_link_url(web_url, link.id),
        "expires_at": link.gmt_expires,
    }


@router.get("/{sandbox_id}/web-link", response_model=SandboxWebLinkStatusResponse)
async def get_sandbox_web_link(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    sandbox, link = await _get_owned_sandbox_with_active_web_link(session, sandbox_id, user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)
    set_request_context(request, sandbox_id=sandbox.id)

    web_url = _get_web_url(sandbox, public_control_plane_base_url(request))
    if link is None:
        return {"web_url": web_url, "enabled": False, "expires_at": None, "last_used_at": None}
    return {
        "web_url": web_url,
        "enabled": True,
        "expires_at": link.gmt_expires,
        "last_used_at": link.gmt_last_used,
    }


@router.delete("/{sandbox_id}/web-link", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sandbox_web_link(
    request: Request,
    sandbox_id: str,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
):
    sandbox, link = await _get_owned_sandbox_with_active_web_link(session, sandbox_id, user.id)
    if sandbox is None:
        raise SandboxNotFoundError(sandbox_id)
    set_request_context(request, sandbox_id=sandbox.id)

    if link is not None:
        link.gmt_deleted = utc_now()
        link.gmt_updated = utc_now()
        session.add(link)
        await record_audit_event(
            session,
            action="sandbox.web_link.delete",
            target_type="sandbox",
            target_id=sandbox.id,
            metadata={"issued_via": "open_link"},
            request=request,
        )
        await session.commit()
