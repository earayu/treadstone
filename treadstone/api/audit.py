from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import bearer_scheme, optional_cookie_user
from treadstone.api.schemas import AuditEventListResponse, AuditFilterOptionsResponse
from treadstone.core.database import get_session
from treadstone.core.errors import AuthRequiredError, ForbiddenError
from treadstone.core.request_context import set_request_context
from treadstone.models.audit_event import AuditEvent
from treadstone.models.user import User
from treadstone.services.audit import record_audit_event

router = APIRouter(prefix="/v1/audit", tags=["audit"])


def _apply_filters(
    statement,
    *,
    action: str | None,
    target_type: str | None,
    target_id: str | None,
    actor_user_id: str | None,
    request_id: str | None,
    result: str | None,
    since: datetime | None,
    until: datetime | None,
):
    if action is not None:
        statement = statement.where(AuditEvent.action == action)
    if target_type is not None:
        statement = statement.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        statement = statement.where(AuditEvent.target_id == target_id)
    if actor_user_id is not None:
        statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
    if request_id is not None:
        statement = statement.where(AuditEvent.request_id == request_id)
    if result is not None:
        statement = statement.where(AuditEvent.result == result)
    if since is not None:
        statement = statement.where(AuditEvent.created_at >= since)
    if until is not None:
        statement = statement.where(AuditEvent.created_at <= until)
    return statement


def _serialize_event(event: AuditEvent) -> dict:
    return {
        "id": event.id,
        "created_at": event.created_at,
        "actor_type": event.actor_type,
        "actor_user_id": event.actor_user_id,
        "actor_api_key_id": event.actor_api_key_id,
        "credential_type": event.credential_type,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "result": event.result,
        "error_code": event.error_code,
        "request_id": event.request_id,
        "ip": event.ip,
        "user_agent": event.user_agent,
        "metadata": event.event_metadata,
    }


def _compact_filters(**values: object) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


async def get_audit_session_admin(
    request: Request,
    _credentials=Depends(bearer_scheme),
    cookie_user: User | None = Depends(optional_cookie_user),
) -> User:
    if _credentials is not None:
        raise ForbiddenError("Audit endpoints require an admin session cookie.")
    if cookie_user is None:
        raise AuthRequiredError()
    if cookie_user.role != "admin":
        raise ForbiddenError("Admin required")

    set_request_context(request, actor_user_id=cookie_user.id, credential_type="cookie")
    return cookie_user


@router.get("/filter-options", response_model=AuditFilterOptionsResponse)
async def get_audit_filter_options(
    request: Request,
    admin: User = Depends(get_audit_session_admin),
    session: AsyncSession = Depends(get_session),
):
    actions = (await session.execute(select(AuditEvent.action).distinct().order_by(AuditEvent.action))).scalars().all()
    target_types = (
        (await session.execute(select(AuditEvent.target_type).distinct().order_by(AuditEvent.target_type)))
        .scalars()
        .all()
    )
    results = (await session.execute(select(AuditEvent.result).distinct().order_by(AuditEvent.result))).scalars().all()
    await record_audit_event(
        session,
        action="audit.filter_options.read",
        target_type="audit_event",
        actor_user_id=admin.id,
        credential_type="cookie",
        metadata={"actions": len(actions), "target_types": len(target_types), "results": len(results)},
        request=request,
    )
    await session.commit()
    return {"actions": actions, "target_types": target_types, "results": results}


@router.get("/events", response_model=AuditEventListResponse)
async def list_audit_events(
    request: Request,
    admin: User = Depends(get_audit_session_admin),
    session: AsyncSession = Depends(get_session),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    actor_email: str | None = Query(default=None),
    request_id: str | None = Query(default=None),
    result: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    resolved_actor_user_id = actor_user_id
    if actor_email and not actor_user_id:
        user_row = await session.execute(select(User).where(User.email == actor_email))
        user = user_row.unique().scalar_one_or_none()
        if user:
            resolved_actor_user_id = user.id
        else:
            return {"items": [], "total": 0}

    base_statement = _apply_filters(
        select(AuditEvent),
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=resolved_actor_user_id,
        request_id=request_id,
        result=result,
        since=since,
        until=until,
    )
    items_result = await session.execute(
        base_statement.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
    )
    total_statement = _apply_filters(
        select(func.count()).select_from(AuditEvent),
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=resolved_actor_user_id,
        request_id=request_id,
        result=result,
        since=since,
        until=until,
    )
    total = (await session.execute(total_statement)).scalar_one()
    filters = _compact_filters(
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=resolved_actor_user_id,
        actor_email=actor_email,
        request_id=request_id,
        result=result,
        since=since.isoformat() if since is not None else None,
        until=until.isoformat() if until is not None else None,
    )
    await record_audit_event(
        session,
        action="audit.events.read",
        target_type="audit_event",
        actor_user_id=admin.id,
        credential_type="cookie",
        metadata={"filters": filters, "limit": limit, "offset": offset, "matched_total": total},
        request=request,
    )
    await session.commit()
    return {"items": [_serialize_event(event) for event in items_result.scalars().all()], "total": total}
