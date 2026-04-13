from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.identity.models.cli_login_flow import CliLoginFlow
from treadstone.identity.models.user import utc_now

__all__ = [
    "approve_cli_flow",
    "consume_cli_flow",
]


async def approve_cli_flow(
    session: AsyncSession,
    *,
    flow_id: str,
    user_id: str,
    provider: str,
) -> bool:
    result = await session.execute(
        update(CliLoginFlow)
        .where(
            CliLoginFlow.id == flow_id,
            CliLoginFlow.status == "pending",
        )
        .values(
            status="approved",
            user_id=user_id,
            provider=provider,
            gmt_completed=utc_now(),
        )
    )
    return (result.rowcount or 0) == 1


async def consume_cli_flow(session: AsyncSession, *, flow_id: str) -> bool:
    result = await session.execute(
        update(CliLoginFlow)
        .where(
            CliLoginFlow.id == flow_id,
            CliLoginFlow.status == "approved",
        )
        .values(status="used")
    )
    return (result.rowcount or 0) == 1
