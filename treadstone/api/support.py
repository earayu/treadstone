"""Support feedback API — authenticated users submit messages from the console."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import get_current_control_plane_user
from treadstone.api.schemas import CreateFeedbackRequest, CreateFeedbackResponse
from treadstone.core.database import get_session
from treadstone.core.errors import ConflictError
from treadstone.models.user import User
from treadstone.models.user_feedback import UserFeedback
from treadstone.services.audit import record_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/support", tags=["support"])


@router.post("/feedback", response_model=CreateFeedbackResponse, status_code=201)
async def create_feedback(
    body: CreateFeedbackRequest,
    request: Request,
    user: User = Depends(get_current_control_plane_user),
    session: AsyncSession = Depends(get_session),
) -> CreateFeedbackResponse:
    """Submit support or product feedback (requires login)."""
    row = UserFeedback(
        user_id=user.id,
        email=user.email,
        body=body.body,
    )
    session.add(row)

    try:
        await session.flush()
        await record_audit_event(
            session,
            action="feedback.create",
            target_type="user_feedback",
            target_id=row.id,
            actor_user_id=user.id,
            request=request,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.exception("Failed to persist user feedback")
        raise ConflictError("Could not save feedback. Please try again.") from None

    return CreateFeedbackResponse(id=row.id)
