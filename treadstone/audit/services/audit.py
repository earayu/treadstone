from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.audit.models.audit_event import AuditActorType, AuditEvent, AuditResult
from treadstone.core.request_context import get_client_ip, get_request_context

__all__ = [
    "record_audit_event",
]


def _compact(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    return {key: value for key, value in metadata.items() if value is not None}


async def record_audit_event(
    session: AsyncSession,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    result: str = AuditResult.SUCCESS.value,
    actor_type: str | None = None,
    actor_user_id: str | None = None,
    actor_api_key_id: str | None = None,
    credential_type: str | None = None,
    error_code: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    request_actor_user_id = actor_user_id
    request_actor_api_key_id = actor_api_key_id
    request_credential_type = credential_type
    request_id = None
    ip = None
    user_agent = None

    if request is not None:
        request_actor_user_id = request_actor_user_id or get_request_context(request, "actor_user_id")
        request_actor_api_key_id = request_actor_api_key_id or get_request_context(request, "actor_api_key_id")
        request_credential_type = request_credential_type or get_request_context(request, "credential_type")
        request_id = get_request_context(request, "request_id")
        ip = get_client_ip(request.scope)
        user_agent = request.headers.get("user-agent")

    resolved_actor_type = actor_type
    if resolved_actor_type is None:
        resolved_actor_type = AuditActorType.SYSTEM.value if request is None else AuditActorType.USER.value

    event = AuditEvent(
        actor_type=resolved_actor_type,
        actor_user_id=request_actor_user_id,
        actor_api_key_id=request_actor_api_key_id,
        credential_type=request_credential_type,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        error_code=error_code,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        event_metadata=_compact(metadata),
    )
    session.add(event)
    return event
