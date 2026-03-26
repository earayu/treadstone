"""MeteringService — core metering logic for the Treadstone billing system.

Implements Layer 1 of the metering execution plan:
  F05: Plan management (ensure_user_plan, get_user_plan, update_user_tier)
  F06: Welcome bonus (auto-granted on free-tier registration)
  F07: Dual-pool credit consumption (consume_compute_credits)
  F08: Compute session lifecycle (open_compute_session, close_compute_session)
  F09: Storage ledger (record_storage_allocation, record_storage_release)

Transaction Policy
------------------
Methods modify ORM objects but do NOT commit the session.
Callers are responsible for committing or rolling back.  This keeps
transaction boundaries explicit and composable — e.g. k8s_sync can
update sandbox state and open a compute session in the same atomic
transaction.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.core.errors import NotFoundError, ValidationError
from treadstone.models.metering import (
    ComputeSession,
    CreditGrant,
    StorageLedger,
    StorageState,
    TierTemplate,
    UserPlan,
)
from treadstone.models.user import utc_now
from treadstone.services.metering_helpers import (
    ConsumeResult,
    calculate_credit_rate,
    compute_period_bounds,
)

logger = logging.getLogger(__name__)

WELCOME_BONUS_AMOUNT = Decimal("50")
WELCOME_BONUS_EXPIRY_DAYS = 90

ALLOWED_PLAN_OVERRIDES = frozenset(
    {
        "compute_credits_monthly_limit",
        "storage_credits_monthly_limit",
        "max_concurrent_running",
        "max_sandbox_duration_seconds",
        "allowed_templates",
        "grace_period_seconds",
    }
)


class MeteringService:
    """Core metering service for quota management and resource tracking."""

    # ═══════════════════════════════════════════════════════
    #  Plan Management  (F05)
    # ═══════════════════════════════════════════════════════

    async def ensure_user_plan(
        self,
        session: AsyncSession,
        user_id: str,
        tier: str = "free",
    ) -> UserPlan:
        """Get or create a UserPlan for the user.

        Idempotent: returns the existing plan if one already exists.
        On first creation, copies defaults from TierTemplate and issues
        a welcome-bonus CreditGrant for free-tier users (F06).
        """
        result = await session.execute(select(UserPlan).where(UserPlan.user_id == user_id))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        template = await self._get_tier_template(session, tier)
        now = utc_now()
        period_start, period_end = compute_period_bounds(now)

        plan = UserPlan(
            user_id=user_id,
            tier=template.tier_name,
            compute_credits_monthly_limit=template.compute_credits_monthly,
            storage_credits_monthly_limit=template.storage_credits_monthly,
            max_concurrent_running=template.max_concurrent_running,
            max_sandbox_duration_seconds=template.max_sandbox_duration_seconds,
            allowed_templates=list(template.allowed_templates),
            grace_period_seconds=template.grace_period_seconds,
            period_start=period_start,
            period_end=period_end,
        )

        try:
            async with session.begin_nested():
                session.add(plan)
                if tier == "free":
                    self._create_welcome_bonus(session, user_id, now)
                await session.flush()
        except IntegrityError:
            # A concurrent request already created the plan — return the winner.
            result = await session.execute(select(UserPlan).where(UserPlan.user_id == user_id))
            return result.scalar_one()

        return plan

    async def get_user_plan(self, session: AsyncSession, user_id: str) -> UserPlan:
        """Get the user's plan, auto-creating a free plan if none exists."""
        return await self.ensure_user_plan(session, user_id)

    async def update_user_tier(
        self,
        session: AsyncSession,
        user_id: str,
        new_tier: str,
        overrides: dict | None = None,
    ) -> UserPlan:
        """Change a user's tier and optionally apply admin overrides.

        Loads defaults from TierTemplate for the new tier, then overlays
        any override values provided.  When the user has no plan yet,
        creates one directly with the target tier (avoids minting an
        unwanted free-tier welcome bonus).
        """
        template = await self._get_tier_template(session, new_tier)

        result = await session.execute(select(UserPlan).where(UserPlan.user_id == user_id))
        plan = result.scalar_one_or_none()

        if plan is None:
            # Try to create with the target tier (avoids free-tier welcome bonus).
            # If a concurrent request already created a free plan, ensure_user_plan
            # returns that plan; the update below corrects the tier either way.
            plan = await self.ensure_user_plan(session, user_id, tier=new_tier)

        now = utc_now()

        plan.tier = template.tier_name
        plan.compute_credits_monthly_limit = template.compute_credits_monthly
        plan.storage_credits_monthly_limit = template.storage_credits_monthly
        plan.max_concurrent_running = template.max_concurrent_running
        plan.max_sandbox_duration_seconds = template.max_sandbox_duration_seconds
        plan.allowed_templates = list(template.allowed_templates)
        plan.grace_period_seconds = template.grace_period_seconds
        plan.gmt_updated = now

        if overrides:
            self._apply_overrides(plan, overrides)
            plan.overrides = overrides

        session.add(plan)
        await session.flush()
        return plan

    # ═══════════════════════════════════════════════════════
    #  Welcome Bonus  (F06)
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def _create_welcome_bonus(
        session: AsyncSession,
        user_id: str,
        now: datetime,
    ) -> CreditGrant:
        """Create a welcome-bonus CreditGrant (50 compute credits, 90 days)."""
        grant = CreditGrant(
            user_id=user_id,
            credit_type="compute",
            grant_type="welcome_bonus",
            original_amount=WELCOME_BONUS_AMOUNT,
            remaining_amount=WELCOME_BONUS_AMOUNT,
            reason="Welcome bonus for new users",
            granted_at=now,
            expires_at=now + timedelta(days=WELCOME_BONUS_EXPIRY_DAYS),
        )
        session.add(grant)
        return grant

    # ═══════════════════════════════════════════════════════
    #  Dual-Pool Credit Consumption  (F07)
    # ═══════════════════════════════════════════════════════

    async def consume_compute_credits(
        self,
        session: AsyncSession,
        user_id: str,
        amount: Decimal,
    ) -> ConsumeResult:
        """Consume compute credits using the dual-pool algorithm.

        Deduction order:
          1. Monthly pool  (UserPlan.compute_credits_monthly_used)
          2. Extra pool    (CreditGrant rows, FIFO by expires_at ASC NULLS LAST)

        CreditGrant rows are locked with SELECT … FOR UPDATE to prevent
        concurrent over-deduction during leader-overlap or admin operations.

        A positive ``shortfall`` in the result means both pools are exhausted.
        """
        if amount <= Decimal("0"):
            return ConsumeResult(monthly=Decimal("0"), extra=Decimal("0"), shortfall=Decimal("0"))

        plan = await self._get_user_plan_for_update(session, user_id)
        monthly_remaining = plan.compute_credits_monthly_limit - plan.compute_credits_monthly_used

        # ── Phase 1: Monthly pool ──
        if monthly_remaining >= amount:
            plan.compute_credits_monthly_used += amount
            plan.gmt_updated = utc_now()
            session.add(plan)
            return ConsumeResult(monthly=amount, extra=Decimal("0"), shortfall=Decimal("0"))

        monthly_consumed = max(Decimal("0"), monthly_remaining)
        extra_needed = amount - monthly_consumed

        if monthly_consumed > Decimal("0"):
            plan.compute_credits_monthly_used = plan.compute_credits_monthly_limit
            plan.gmt_updated = utc_now()
            session.add(plan)

        # ── Phase 2: Extra pool (CreditGrant FIFO) ──
        now = utc_now()
        result = await session.execute(
            select(CreditGrant)
            .where(
                CreditGrant.user_id == user_id,
                CreditGrant.credit_type == "compute",
                CreditGrant.remaining_amount > 0,
                or_(
                    CreditGrant.expires_at.is_(None),
                    CreditGrant.expires_at > now,
                ),
            )
            .order_by(CreditGrant.expires_at.asc().nulls_last())
            .with_for_update()
        )
        grants = result.scalars().all()

        extra_consumed = Decimal("0")
        for grant in grants:
            if extra_needed <= Decimal("0"):
                break
            deduct = min(grant.remaining_amount, extra_needed)
            grant.remaining_amount -= deduct
            grant.gmt_updated = now
            session.add(grant)
            extra_consumed += deduct
            extra_needed -= deduct

        shortfall = max(Decimal("0"), extra_needed)
        return ConsumeResult(monthly=monthly_consumed, extra=extra_consumed, shortfall=shortfall)

    # ═══════════════════════════════════════════════════════
    #  Compute Session Lifecycle  (F08)
    # ═══════════════════════════════════════════════════════

    async def open_compute_session(
        self,
        session: AsyncSession,
        sandbox_id: str,
        user_id: str,
        template: str,
    ) -> ComputeSession:
        """Open a new ComputeSession when a sandbox enters the ready state.

        Idempotent: if an open session already exists for this sandbox it is
        returned instead of creating a duplicate.  The existing-row check
        uses ``FOR UPDATE`` so that concurrent Watch + Reconcile callers
        serialize rather than both inserting.

        The credit rate is locked at open time based on the template spec;
        subsequent pricing changes do not affect this session.
        """
        result = await session.execute(
            select(ComputeSession)
            .where(
                ComputeSession.sandbox_id == sandbox_id,
                ComputeSession.ended_at.is_(None),
            )
            .with_for_update()
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        credit_rate = calculate_credit_rate(template)
        now = utc_now()

        cs = ComputeSession(
            sandbox_id=sandbox_id,
            user_id=user_id,
            template=template,
            credit_rate_per_hour=credit_rate,
            started_at=now,
            last_metered_at=now,
        )
        session.add(cs)
        await session.flush()
        return cs

    async def close_compute_session(
        self,
        session: AsyncSession,
        sandbox_id: str,
    ) -> ComputeSession | None:
        """Close the open ComputeSession for a sandbox.

        Calculates final credits from ``last_metered_at`` → now, consumes
        them through the dual-pool algorithm, and sets ``ended_at``.

        Idempotent: returns ``None`` if no open session exists.
        """
        result = await session.execute(
            select(ComputeSession)
            .where(
                ComputeSession.sandbox_id == sandbox_id,
                ComputeSession.ended_at.is_(None),
            )
            .with_for_update()
        )
        cs = result.scalar_one_or_none()
        if cs is None:
            return None

        now = utc_now()
        elapsed_seconds = (now - cs.last_metered_at).total_seconds()

        if elapsed_seconds > 0:
            final_credits = Decimal(str(elapsed_seconds)) / Decimal("3600") * cs.credit_rate_per_hour
            consume_result = await self.consume_compute_credits(session, cs.user_id, final_credits)
            cs.credits_consumed += final_credits
            cs.credits_consumed_monthly += consume_result.monthly
            cs.credits_consumed_extra += consume_result.extra

        cs.ended_at = now
        cs.last_metered_at = now
        cs.gmt_updated = now
        session.add(cs)
        await session.flush()
        return cs

    # ═══════════════════════════════════════════════════════
    #  Storage Ledger  (F09)
    # ═══════════════════════════════════════════════════════

    async def record_storage_allocation(
        self,
        session: AsyncSession,
        user_id: str,
        sandbox_id: str,
        size_gib: int,
    ) -> StorageLedger:
        """Record a new storage allocation for a persistent sandbox."""
        now = utc_now()
        ledger = StorageLedger(
            user_id=user_id,
            sandbox_id=sandbox_id,
            size_gib=size_gib,
            storage_state=StorageState.ACTIVE,
            allocated_at=now,
            last_metered_at=now,
        )
        session.add(ledger)
        await session.flush()
        return ledger

    async def record_storage_release(
        self,
        session: AsyncSession,
        sandbox_id: str,
    ) -> StorageLedger | None:
        """Record storage release when a persistent sandbox is deleted.

        Transitions the entry to DELETED, calculates final GiB-hours,
        and sets ``released_at``.

        Idempotent: returns ``None`` if no active entry exists.
        """
        result = await session.execute(
            select(StorageLedger).where(
                StorageLedger.sandbox_id == sandbox_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
        )
        ledger = result.scalar_one_or_none()
        if ledger is None:
            return None

        now = utc_now()
        elapsed_seconds = (now - ledger.last_metered_at).total_seconds()
        if elapsed_seconds > 0:
            final_gib_hours = Decimal(str(ledger.size_gib)) * Decimal(str(elapsed_seconds)) / Decimal("3600")
            ledger.gib_hours_consumed += final_gib_hours.quantize(Decimal("0.0001"))

        ledger.storage_state = StorageState.DELETED
        ledger.released_at = now
        ledger.last_metered_at = now
        ledger.gmt_updated = now
        session.add(ledger)
        await session.flush()
        return ledger

    # ═══════════════════════════════════════════════════════
    #  Query Helpers
    # ═══════════════════════════════════════════════════════

    async def get_extra_credits_remaining(
        self,
        session: AsyncSession,
        user_id: str,
        credit_type: str,
    ) -> Decimal:
        """Sum remaining amounts of all unexpired CreditGrants for the given type."""
        now = utc_now()
        result = await session.execute(
            select(func.coalesce(func.sum(CreditGrant.remaining_amount), 0)).where(
                CreditGrant.user_id == user_id,
                CreditGrant.credit_type == credit_type,
                CreditGrant.remaining_amount > 0,
                or_(
                    CreditGrant.expires_at.is_(None),
                    CreditGrant.expires_at > now,
                ),
            )
        )
        return Decimal(str(result.scalar_one()))

    async def _get_user_plan_for_update(self, session: AsyncSession, user_id: str) -> UserPlan:
        """Fetch and row-lock the user's plan for credit mutation.

        If no plan exists yet (pre-metering user), one is auto-created
        first, then re-fetched with FOR UPDATE.
        """
        result = await session.execute(select(UserPlan).where(UserPlan.user_id == user_id).with_for_update())
        plan = result.scalar_one_or_none()
        if plan is not None:
            return plan
        await self.ensure_user_plan(session, user_id)
        result = await session.execute(select(UserPlan).where(UserPlan.user_id == user_id).with_for_update())
        return result.scalar_one()

    async def _get_tier_template(self, session: AsyncSession, tier_name: str) -> TierTemplate:
        """Fetch an active TierTemplate by name.

        Raises NotFoundError when the tier does not exist or has been
        soft-disabled (``is_active = False``).
        """
        result = await session.execute(
            select(TierTemplate).where(
                TierTemplate.tier_name == tier_name,
                TierTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise NotFoundError("TierTemplate", tier_name)
        return template

    @staticmethod
    def _apply_overrides(plan: UserPlan, overrides: dict) -> None:
        """Apply admin override values to a UserPlan, validating keys first."""
        for key in overrides:
            if key not in ALLOWED_PLAN_OVERRIDES:
                raise ValidationError(
                    f"Invalid override key: '{key}'. Allowed keys: {', '.join(sorted(ALLOWED_PLAN_OVERRIDES))}"
                )
        for key, value in overrides.items():
            setattr(plan, key, value)
