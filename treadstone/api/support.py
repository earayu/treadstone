"""Support feedback API — authenticated users submit messages from the console."""

from __future__ import annotations

import logging
from datetime import UTC

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.api.deps import optional_cookie_user
from treadstone.api.schemas import CreateFeedbackRequest, CreateFeedbackResponse
from treadstone.core.database import get_session
from treadstone.core.errors import AuthRequiredError, ConflictError, FeedbackRateLimitError
from treadstone.core.request_context import set_request_context
from treadstone.models.user import User, utc_now
from treadstone.models.user_feedback import UserFeedback
from treadstone.services.audit import record_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/support", tags=["support"])
FEEDBACK_SUBMISSION_COOLDOWN_SECONDS = 60


@router.post("/feedback", response_model=CreateFeedbackResponse, status_code=201)
async def create_feedback(
    body: CreateFeedbackRequest,
    request: Request,
    user: User | None = Depends(optional_cookie_user),
    session: AsyncSession = Depends(get_session),
) -> CreateFeedbackResponse:
    """Submit support or product feedback from an interactive browser session."""
    if user is None:
        raise AuthRequiredError("Support feedback requires an active browser session.")

    set_request_context(request, actor_user_id=user.id, credential_type="cookie")
    latest_created = (
        await session.execute(
            select(UserFeedback.gmt_created)
            .where(UserFeedback.user_id == user.id)
            .order_by(UserFeedback.gmt_created.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_created is not None:
        now = utc_now()
        if latest_created.tzinfo is None:
            latest_created = latest_created.replace(tzinfo=UTC)
        elapsed = (now - latest_created).total_seconds()
        if elapsed < FEEDBACK_SUBMISSION_COOLDOWN_SECONDS:
            wait_seconds = max(1, int(FEEDBACK_SUBMISSION_COOLDOWN_SECONDS - elapsed))
            await record_audit_event(
                session,
                action="feedback.create",
                target_type="user_feedback",
                result="failure",
                error_code="feedback_rate_limited",
                request=request,
            )
            await session.commit()
            raise FeedbackRateLimitError(wait_seconds)

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
