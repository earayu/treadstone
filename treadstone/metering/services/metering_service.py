"""MeteringService — core metering logic for the Treadstone billing system.

Implements Layers 1–2 of the metering execution plan:
  F05: Plan management (ensure_user_plan, get_user_plan, update_user_tier)
  F06: Welcome bonus (auto-granted on free-tier registration)
  F07: Dual-pool credit consumption (consume_compute_credits)
  F08: Compute session lifecycle (open_compute_session, close_compute_session)
  F09: Storage ledger (record_storage_allocation, record_storage_release)
  F10: Template permission check (check_template_allowed)
  F11: Compute quota check (check_compute_quota, get_total_compute_remaining)
  F12: Concurrent sandbox limit (check_concurrent_limit)
  F13: Storage quota check (check_storage_quota, get_total_storage_quota, get_current_storage_used)
  F14: Sandbox duration check (check_sandbox_duration)

Transaction Policy
------------------
Methods modify ORM objects but do NOT commit the session.
Callers are responsible for committing or rolling back.  This keeps
transaction boundaries explicit and composable.

Note: in k8s_sync, ``_optimistic_update`` commits the sandbox status
change in its own transaction, so the subsequent metering call runs
in a separate implicit transaction.  If the metering call fails, the
sandbox status is already committed but the ComputeSession may be
missing.  ``reconcile_metering()`` repairs such mismatches, providing
eventual consistency.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.core.errors import (
    ComputeQuotaExceededError,
    ConcurrentLimitError,
    NotFoundError,
    StorageQuotaExceededError,
    TemplateNotAllowedError,
    ValidationError,
)
from treadstone.identity.models.user import utc_now
from treadstone.metering.models.metering import (
    ComputeGrant,
    ComputeSession,
    StorageLedger,
    StorageQuotaGrant,
    StorageState,
    TierTemplate,
    UserPlan,
)
from treadstone.metering.services.metering_helpers import (
    CU_MEMORY_WEIGHT,
    CU_VCPU_WEIGHT,
    ConsumeResult,
    calculate_cu_rate,
    compute_period_bounds,
    get_template_resource_spec,
)
from treadstone.sandbox.models.sandbox import Sandbox, SandboxStatus

__all__ = [
    "MeteringService",
    "ALLOWED_PLAN_OVERRIDES",
    "MAX_CLOSE_DELTA_SECONDS",
    "WELCOME_BONUS_AMOUNT",
    "WELCOME_BONUS_EXPIRY_DAYS",
]

MAX_CLOSE_DELTA_SECONDS = 120

logger = logging.getLogger(__name__)

WELCOME_BONUS_AMOUNT = Decimal("0")
WELCOME_BONUS_EXPIRY_DAYS = 90

ALLOWED_PLAN_OVERRIDES = frozenset(
    {
        "compute_units_monthly_limit",
        "storage_capacity_limit_gib",
        "max_concurrent_running",
        "max_sandbox_duration_seconds",
        "allowed_templates",
        "grace_period_seconds",
    }
)


def _coerce_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class MeteringService:
    """Core metering service for quota management and resource tracking."""

    async def _get_usage_summary_snapshot(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> tuple[UserPlan, int, int, int, Decimal]:
        now = utc_now()
        statement = select(
            UserPlan,
            select(func.coalesce(func.sum(StorageQuotaGrant.size_gib), 0))
            .where(
                StorageQuotaGrant.user_id == user_id,
                or_(
                    StorageQuotaGrant.expires_at.is_(None),
                    StorageQuotaGrant.expires_at > now,
                ),
            )
            .scalar_subquery()
            .label("extra_storage"),
            select(func.coalesce(func.sum(StorageLedger.size_gib), 0))
            .where(
                StorageLedger.user_id == user_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
            .scalar_subquery()
            .label("current_storage_used"),
            select(func.count())
            .select_from(Sandbox)
            .where(
                Sandbox.owner_id == user_id,
                Sandbox.status.in_([SandboxStatus.CREATING, SandboxStatus.READY]),
            )
            .scalar_subquery()
            .label("running_count"),
            select(func.coalesce(func.sum(ComputeGrant.remaining_amount), 0))
            .where(
                ComputeGrant.user_id == user_id,
                ComputeGrant.remaining_amount > 0,
                or_(
                    ComputeGrant.expires_at.is_(None),
                    ComputeGrant.expires_at > now,
                ),
            )
            .scalar_subquery()
            .label("extra_compute_remaining"),
        ).where(UserPlan.user_id == user_id)

        result = await session.execute(statement)
        row = result.one_or_none()
        if row is None:
            await self.ensure_user_plan(session, user_id)
            result = await session.execute(statement)
            row = result.one()

        plan, extra_storage, current_storage_used, running_count, extra_compute_remaining = row
        return (
            plan,
            int(extra_storage or 0),
            int(current_storage_used or 0),
            int(running_count or 0),
            Decimal(str(extra_compute_remaining or 0)),
        )

    @staticmethod
    def _period_overlap_ratio(
        started_at: datetime,
        ended_at: datetime | None,
        *,
        now: datetime,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """Return the fraction of an entry's accumulated usage that falls inside the billing period."""
        tzinfo = now.tzinfo
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=tzinfo)
        if ended_at is not None and ended_at.tzinfo is None:
            ended_at = ended_at.replace(tzinfo=tzinfo)
        if period_start.tzinfo is None:
            period_start = period_start.replace(tzinfo=tzinfo)
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=tzinfo)

        effective_end = min(ended_at or now, now, period_end)
        if effective_end <= started_at:
            return Decimal("0")

        overlap_start = max(started_at, period_start)
        overlap_end = min(effective_end, period_end)
        if overlap_end <= overlap_start:
            return Decimal("0")

        total_seconds = Decimal(str((effective_end - started_at).total_seconds()))
        overlap_seconds = Decimal(str((overlap_end - overlap_start).total_seconds()))
        if total_seconds <= Decimal("0"):
            return Decimal("0")
        return overlap_seconds / total_seconds

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
            compute_units_monthly_limit=template.compute_units_monthly,
            storage_capacity_limit_gib=template.storage_capacity_gib,
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
                if tier == "free" and WELCOME_BONUS_AMOUNT > 0:
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
        plan.compute_units_monthly_limit = template.compute_units_monthly
        plan.storage_capacity_limit_gib = template.storage_capacity_gib
        plan.max_concurrent_running = template.max_concurrent_running
        plan.max_sandbox_duration_seconds = template.max_sandbox_duration_seconds
        plan.allowed_templates = list(template.allowed_templates)
        plan.grace_period_seconds = template.grace_period_seconds
        plan.gmt_updated = now

        if overrides:
            self.apply_overrides(plan, overrides)
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
    ) -> ComputeGrant:
        """Create a welcome-bonus ComputeGrant (50 compute credits, 90 days)."""
        grant = ComputeGrant(
            user_id=user_id,
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
        """Consume Compute Units using the dual-pool algorithm.

        Deduction order:
          1. Monthly pool  (UserPlan.compute_units_monthly_used)
          2. Extra pool    (ComputeGrant rows, FIFO by expires_at ASC NULLS LAST)

        ComputeGrant rows are locked with SELECT ... FOR UPDATE to prevent
        concurrent over-deduction during leader-overlap or admin operations.

        A positive ``shortfall`` in the result means both pools are exhausted.
        """
        if amount <= Decimal("0"):
            return ConsumeResult(monthly=Decimal("0"), extra=Decimal("0"), shortfall=Decimal("0"))

        plan = await self._get_user_plan_for_update(session, user_id)
        monthly_remaining = plan.compute_units_monthly_limit - plan.compute_units_monthly_used

        # ── Phase 1: Monthly pool ──
        if monthly_remaining >= amount:
            plan.compute_units_monthly_used += amount
            plan.gmt_updated = utc_now()
            session.add(plan)
            return ConsumeResult(monthly=amount, extra=Decimal("0"), shortfall=Decimal("0"))

        monthly_consumed = max(Decimal("0"), monthly_remaining)
        extra_needed = amount - monthly_consumed

        if monthly_consumed > Decimal("0"):
            plan.compute_units_monthly_used = plan.compute_units_monthly_limit
            plan.gmt_updated = utc_now()
            session.add(plan)

        # ── Phase 2: Extra pool (ComputeGrant FIFO) ──
        now = utc_now()
        result = await session.execute(
            select(ComputeGrant)
            .where(
                ComputeGrant.user_id == user_id,
                ComputeGrant.remaining_amount > 0,
                or_(
                    ComputeGrant.expires_at.is_(None),
                    ComputeGrant.expires_at > now,
                ),
            )
            .order_by(ComputeGrant.expires_at.asc().nulls_last())
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

        if shortfall > Decimal("0"):
            plan.compute_units_overage = (plan.compute_units_overage or Decimal("0")) + shortfall
            plan.gmt_updated = utc_now()
            session.add(plan)

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

        Raw resource specs (vCPU, memory) are locked at open time from the
        template spec; subsequent spec changes do not affect this session.
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

        vcpu, memory_gib = get_template_resource_spec(template)
        now = utc_now()

        cs = ComputeSession(
            sandbox_id=sandbox_id,
            user_id=user_id,
            template=template,
            vcpu_request=vcpu,
            memory_gib_request=memory_gib,
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

        Accumulates final raw resource-hours from ``last_metered_at`` → now,
        sets ``ended_at``, and consumes the corresponding credit delta from
        the user's dual pool (monthly first, then ComputeGrant FIFO).

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
        elapsed_seconds = (now - _coerce_utc(cs.last_metered_at)).total_seconds()

        if elapsed_seconds > MAX_CLOSE_DELTA_SECONDS:
            logger.warning(
                "ComputeSession %s close delta %ds exceeds cap %ds (possible leader downtime), capping",
                cs.id,
                int(elapsed_seconds),
                MAX_CLOSE_DELTA_SECONDS,
            )
            elapsed_seconds = MAX_CLOSE_DELTA_SECONDS

        if elapsed_seconds > 0:
            elapsed_hours = Decimal(str(elapsed_seconds)) / Decimal("3600")
            cs.vcpu_hours += cs.vcpu_request * elapsed_hours
            cs.memory_gib_hours += cs.memory_gib_request * elapsed_hours

            cu_rate = calculate_cu_rate(cs.template)
            cu_delta = cu_rate * elapsed_hours
            if cu_delta > Decimal("0"):
                await self.consume_compute_credits(session, cs.user_id, cu_delta)

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
        *,
        backend_mode: str = "live_disk",
    ) -> StorageLedger:
        """Record a new storage allocation for a persistent sandbox.

        Idempotent: if an ACTIVE entry already exists for this sandbox it is
        returned instead of creating a duplicate.  The existing-row check
        uses ``FOR UPDATE`` so that concurrent callers serialize.
        """
        result = await session.execute(
            select(StorageLedger)
            .where(
                StorageLedger.sandbox_id == sandbox_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
            .with_for_update()
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            if existing.backend_mode != backend_mode:
                existing.backend_mode = backend_mode
                existing.gmt_updated = utc_now()
                session.add(existing)
                await session.flush()
            return existing

        now = utc_now()
        ledger = StorageLedger(
            user_id=user_id,
            sandbox_id=sandbox_id,
            size_gib=size_gib,
            storage_state=StorageState.ACTIVE,
            backend_mode=backend_mode,
            allocated_at=now,
            last_metered_at=now,
        )
        session.add(ledger)
        await session.flush()
        return ledger

    async def update_storage_backend_mode(
        self,
        session: AsyncSession,
        sandbox_id: str,
        backend_mode: str,
    ) -> StorageLedger | None:
        result = await session.execute(
            select(StorageLedger)
            .where(
                StorageLedger.sandbox_id == sandbox_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
            .with_for_update()
        )
        ledger = result.scalar_one_or_none()
        if ledger is None:
            return None

        if ledger.backend_mode == backend_mode:
            return ledger

        ledger.backend_mode = backend_mode
        ledger.gmt_updated = utc_now()
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
            select(StorageLedger)
            .where(
                StorageLedger.sandbox_id == sandbox_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
            .with_for_update()
        )
        ledger = result.scalar_one_or_none()
        if ledger is None:
            return None

        now = utc_now()
        elapsed_seconds = (now - _coerce_utc(ledger.last_metered_at)).total_seconds()
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
    #  Quota Checks  (F10–F14)
    # ═══════════════════════════════════════════════════════

    async def check_template_allowed(
        self,
        session: AsyncSession,
        user_id: str,
        template: str,
    ) -> None:
        """Verify that the user's tier permits the requested sandbox template.

        Raises TemplateNotAllowedError (403) if the template is not in the
        plan's ``allowed_templates`` list.
        """
        plan = await self.get_user_plan(session, user_id)
        if template not in plan.allowed_templates:
            raise TemplateNotAllowedError(plan.tier, template, plan.allowed_templates)

    async def check_compute_quota(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> None:
        """Verify that the user has remaining Compute Units.

        Checks monthly remaining + extra ComputeGrants.
        Raises ComputeQuotaExceededError (402) when total_remaining <= 0.
        """
        plan = await self.get_user_plan(session, user_id)
        monthly_remaining = plan.compute_units_monthly_limit - plan.compute_units_monthly_used
        extra_remaining = await self.get_extra_compute_remaining(session, user_id)
        total_remaining = monthly_remaining + extra_remaining - (plan.compute_units_overage or Decimal("0"))
        if total_remaining <= Decimal("0"):
            raise ComputeQuotaExceededError(
                monthly_used=float(plan.compute_units_monthly_used),
                monthly_limit=float(plan.compute_units_monthly_limit),
                extra_remaining=float(extra_remaining),
            )

    async def check_concurrent_limit(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> None:
        """Verify that the user has not reached the concurrent sandbox limit.

        Counts sandboxes in ``creating`` or ``ready`` status.
        Raises ConcurrentLimitError (429) when running >= max_concurrent_running.

        Acquires a FOR UPDATE lock on UserPlan to serialize concurrent
        create/start requests for the same user, preventing TOCTOU races.
        """
        plan = await self._get_user_plan_for_update(session, user_id)
        running_count = await self._count_running_sandboxes(session, user_id)
        if running_count >= plan.max_concurrent_running:
            raise ConcurrentLimitError(running_count, plan.max_concurrent_running)

    async def check_storage_quota(
        self,
        session: AsyncSession,
        user_id: str,
        requested_gib: int,
    ) -> None:
        """Verify that the user has enough storage quota for the requested allocation.

        total_quota = monthly_limit + extra_storage_grants
        available  = total_quota - current_used
        Raises StorageQuotaExceededError (402) when available < requested_gib.

        Relies on the caller having already acquired a FOR UPDATE lock on
        UserPlan (via check_concurrent_limit) to serialize concurrent requests.
        """
        plan = await self.get_user_plan(session, user_id)
        extra_storage = await self.get_extra_storage_quota(session, user_id)
        total_quota = plan.storage_capacity_limit_gib + extra_storage
        current_used = await self.get_current_storage_used(session, user_id)
        available = total_quota - current_used
        if available < requested_gib:
            raise StorageQuotaExceededError(current_used, requested_gib, total_quota)

    async def check_sandbox_duration(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> int:
        """Return the maximum sandbox duration (seconds) allowed by the user's tier.

        The caller is responsible for comparing the returned value against the
        requested ``auto_stop_interval`` and raising ``SandboxDurationExceededError``
        when the request exceeds the limit.  Duration-check semantics
        (e.g. ``auto_stop_interval <= 0`` means unlimited) belong to the sandbox
        domain, not the metering domain.
        """
        plan = await self.get_user_plan(session, user_id)
        return plan.max_sandbox_duration_seconds

    # ═══════════════════════════════════════════════════════
    #  Query Helpers
    # ═══════════════════════════════════════════════════════

    async def get_total_compute_remaining(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> Decimal:
        """Return total Compute Units remaining (monthly + extra - overage).

        Returns negative values during grace-period overage scenarios,
        reflecting the true debt accumulated after both pools are exhausted.
        """
        plan = await self.get_user_plan(session, user_id)
        monthly_remaining = plan.compute_units_monthly_limit - plan.compute_units_monthly_used
        extra_remaining = await self.get_extra_compute_remaining(session, user_id)
        return monthly_remaining + extra_remaining - (plan.compute_units_overage or Decimal("0"))

    async def get_total_storage_quota(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> int:
        """Return total storage quota in GiB (plan limit + active StorageQuotaGrants)."""
        plan = await self.get_user_plan(session, user_id)
        extra_storage = await self.get_extra_storage_quota(session, user_id)
        return plan.storage_capacity_limit_gib + extra_storage

    async def get_current_storage_used(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> int:
        """Return total active storage allocation in GiB.

        Sums ``size_gib`` across all ``ACTIVE`` StorageLedger entries for the user.
        """
        result = await session.execute(
            select(func.coalesce(func.sum(StorageLedger.size_gib), 0)).where(
                StorageLedger.user_id == user_id,
                StorageLedger.storage_state == StorageState.ACTIVE,
            )
        )
        return int(result.scalar_one())

    async def get_extra_compute_remaining(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> Decimal:
        """Sum remaining amounts of all unexpired ComputeGrants."""
        now = utc_now()
        result = await session.execute(
            select(func.coalesce(func.sum(ComputeGrant.remaining_amount), 0)).where(
                ComputeGrant.user_id == user_id,
                ComputeGrant.remaining_amount > 0,
                or_(
                    ComputeGrant.expires_at.is_(None),
                    ComputeGrant.expires_at > now,
                ),
            )
        )
        return Decimal(str(result.scalar_one()))

    async def get_extra_storage_quota(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> int:
        """Sum size_gib of all active (non-expired) StorageQuotaGrants."""
        now = utc_now()
        result = await session.execute(
            select(func.coalesce(func.sum(StorageQuotaGrant.size_gib), 0)).where(
                StorageQuotaGrant.user_id == user_id,
                or_(
                    StorageQuotaGrant.expires_at.is_(None),
                    StorageQuotaGrant.expires_at > now,
                ),
            )
        )
        return int(result.scalar_one())

    async def _count_running_sandboxes(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> int:
        """Count sandboxes in creating or ready status for the given user."""
        result = await session.execute(
            select(func.count())
            .select_from(Sandbox)
            .where(
                Sandbox.owner_id == user_id,
                Sandbox.status.in_([SandboxStatus.CREATING, SandboxStatus.READY]),
            )
        )
        return result.scalar_one()

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

    # ═══════════════════════════════════════════════════════
    #  Usage Queries  (F24)
    # ═══════════════════════════════════════════════════════

    async def get_compute_usage_for_period(
        self,
        session: AsyncSession,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> tuple[Decimal, Decimal]:
        """Sum raw resource-hours from ComputeSessions overlapping a billing period.

        Uses proportional overlap against each session's accumulated totals so
        sessions that straddle a billing boundary contribute only the portion
        that falls inside the requested period.

        Returns (total_vcpu_hours, total_memory_gib_hours).
        """
        now = utc_now()
        result = await session.execute(
            select(ComputeSession).where(
                ComputeSession.user_id == user_id,
                ComputeSession.started_at < period_end,
                or_(ComputeSession.ended_at.is_(None), ComputeSession.ended_at > period_start),
            )
        )
        total_vcpu_hours = Decimal("0")
        total_memory_gib_hours = Decimal("0")
        for compute_session in result.scalars().all():
            overlap_ratio = self._period_overlap_ratio(
                compute_session.started_at,
                compute_session.ended_at,
                now=now,
                period_start=period_start,
                period_end=period_end,
            )
            total_vcpu_hours += compute_session.vcpu_hours * overlap_ratio
            total_memory_gib_hours += compute_session.memory_gib_hours * overlap_ratio

        return total_vcpu_hours, total_memory_gib_hours

    async def get_compute_unit_hours_for_period(
        self,
        session: AsyncSession,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """Sum per-session Compute Unit hours clipped to the billing period overlap."""
        now = utc_now()
        tzinfo = now.tzinfo
        normalized_period_end = period_end if period_end.tzinfo is not None else period_end.replace(tzinfo=tzinfo)
        overlapping = and_(
            ComputeSession.user_id == user_id,
            ComputeSession.started_at < period_end,
            or_(ComputeSession.ended_at.is_(None), ComputeSession.ended_at > period_start),
        )
        active_sessions_are_fully_contained = now <= normalized_period_end
        fully_contained = and_(
            ComputeSession.started_at >= period_start,
            or_(
                ComputeSession.ended_at <= period_end,
                and_(ComputeSession.ended_at.is_(None), active_sessions_are_fully_contained),
            ),
        )
        aggregate_result = await session.execute(
            select(
                func.coalesce(func.sum(ComputeSession.vcpu_hours), 0),
                func.coalesce(func.sum(ComputeSession.memory_gib_hours), 0),
            ).where(overlapping, fully_contained)
        )
        full_vcpu_hours, full_memory_gib_hours = aggregate_result.one()
        total_compute_unit_hours = CU_VCPU_WEIGHT * Decimal(str(full_vcpu_hours or 0)) + CU_MEMORY_WEIGHT * Decimal(
            str(full_memory_gib_hours or 0)
        )
        result = await session.execute(
            select(
                ComputeSession.started_at,
                ComputeSession.ended_at,
                ComputeSession.vcpu_hours,
                ComputeSession.memory_gib_hours,
            ).where(overlapping, not_(fully_contained))
        )
        for started_at, ended_at, vcpu_hours, memory_gib_hours in result.all():
            overlap_ratio = self._period_overlap_ratio(
                started_at,
                ended_at,
                now=now,
                period_start=period_start,
                period_end=period_end,
            )
            session_compute_unit_hours = CU_VCPU_WEIGHT * Decimal(str(vcpu_hours)) + CU_MEMORY_WEIGHT * Decimal(
                str(memory_gib_hours)
            )
            total_compute_unit_hours += session_compute_unit_hours * overlap_ratio

        return total_compute_unit_hours

    async def get_storage_gib_hours_for_period(
        self,
        session: AsyncSession,
        user_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Decimal:
        """Calculate GiB-hours for the given billing period with proper clipping."""
        now = utc_now()
        overlapping = and_(
            StorageLedger.user_id == user_id,
            StorageLedger.allocated_at < period_end,
            or_(StorageLedger.released_at.is_(None), StorageLedger.released_at > period_start),
        )
        fully_contained_released = and_(
            StorageLedger.allocated_at >= period_start,
            StorageLedger.released_at.is_not(None),
            StorageLedger.released_at <= period_end,
        )
        aggregate_result = await session.execute(
            select(func.coalesce(func.sum(StorageLedger.gib_hours_consumed), 0)).where(
                overlapping,
                fully_contained_released,
            )
        )
        total = Decimal(str(aggregate_result.scalar_one() or 0))
        result = await session.execute(
            select(
                StorageLedger.size_gib,
                StorageLedger.allocated_at,
                StorageLedger.released_at,
            ).where(overlapping, not_(fully_contained_released))
        )
        tzinfo = now.tzinfo
        normalized_period_start = (
            period_start if period_start.tzinfo is not None else period_start.replace(tzinfo=tzinfo)
        )
        normalized_period_end = period_end if period_end.tzinfo is not None else period_end.replace(tzinfo=tzinfo)

        for size_gib, allocated_at, released_at in result.all():
            allocated_at = allocated_at if allocated_at.tzinfo is not None else allocated_at.replace(tzinfo=tzinfo)
            if released_at is not None and released_at.tzinfo is None:
                released_at = released_at.replace(tzinfo=tzinfo)

            effective_start = max(allocated_at, normalized_period_start)
            effective_end = min(released_at or now, normalized_period_end, now)
            elapsed_seconds = (effective_end - effective_start).total_seconds()
            if elapsed_seconds > 0:
                total += Decimal(str(size_gib)) * Decimal(str(elapsed_seconds)) / Decimal("3600")

        return total.quantize(Decimal("0.0001"))

    async def get_usage_summary(self, session: AsyncSession, user_id: str) -> dict:
        """Assemble the complete usage overview for GET /v1/usage."""
        (
            plan,
            extra_storage,
            current_storage_used,
            running_count,
            extra_compute_remaining,
        ) = await self._get_usage_summary_snapshot(session, user_id)
        total_storage_quota = plan.storage_capacity_limit_gib + extra_storage

        compute_unit_hours = await self.get_compute_unit_hours_for_period(
            session, user_id, plan.period_start, plan.period_end
        )

        monthly_remaining = max(Decimal("0"), plan.compute_units_monthly_limit - plan.compute_units_monthly_used)
        total_compute_remaining = (
            monthly_remaining + extra_compute_remaining - (plan.compute_units_overage or Decimal("0"))
        )

        storage_gib_hours = await self.get_storage_gib_hours_for_period(
            session, user_id, plan.period_start, plan.period_end
        )

        grace_active = plan.grace_period_started_at is not None
        grace_expires_at = None
        if grace_active and plan.grace_period_started_at is not None:
            grace_expires_at = plan.grace_period_started_at + timedelta(seconds=plan.grace_period_seconds)

        return {
            "tier": plan.tier,
            "billing_period": {
                "start": plan.period_start.isoformat(),
                "end": plan.period_end.isoformat(),
            },
            "compute": {
                "compute_unit_hours": float(compute_unit_hours),
                "monthly_limit": float(plan.compute_units_monthly_limit),
                "monthly_used": float(plan.compute_units_monthly_used),
                "monthly_remaining": float(monthly_remaining),
                "extra_remaining": float(extra_compute_remaining),
                "total_remaining": float(total_compute_remaining),
                "unit": "CU-hours",
            },
            "storage": {
                "gib_hours": float(storage_gib_hours),
                "current_used_gib": current_storage_used,
                "total_quota_gib": total_storage_quota,
                "available_gib": total_storage_quota - current_storage_used,
                "unit": "GiB",
            },
            "limits": {
                "max_concurrent_running": plan.max_concurrent_running,
                "current_running": running_count,
                "max_sandbox_duration_seconds": plan.max_sandbox_duration_seconds,
                "allowed_templates": plan.allowed_templates,
            },
            "grace_period": {
                "active": grace_active,
                "started_at": plan.grace_period_started_at.isoformat() if grace_active else None,
                "expires_at": grace_expires_at.isoformat() if grace_expires_at else None,
                "grace_period_seconds": plan.grace_period_seconds,
            },
        }

    async def list_compute_sessions(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        status: str = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ComputeSession], int]:
        """Return paginated ComputeSession list for a user."""
        base = select(ComputeSession).where(ComputeSession.user_id == user_id)
        count_base = select(func.count()).select_from(ComputeSession).where(ComputeSession.user_id == user_id)
        if status == "active":
            base = base.where(ComputeSession.ended_at.is_(None))
            count_base = count_base.where(ComputeSession.ended_at.is_(None))
        elif status == "completed":
            base = base.where(ComputeSession.ended_at.is_not(None))
            count_base = count_base.where(ComputeSession.ended_at.is_not(None))

        total = (await session.execute(count_base)).scalar_one()
        items_result = await session.execute(
            base.order_by(ComputeSession.started_at.desc()).limit(limit).offset(offset)
        )
        return list(items_result.scalars().all()), total

    async def list_storage_ledger(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        status: str = "all",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[StorageLedger], int]:
        """Return paginated StorageLedger entries for a user."""
        base = select(StorageLedger).where(StorageLedger.user_id == user_id)
        count_base = select(func.count()).select_from(StorageLedger).where(StorageLedger.user_id == user_id)
        if status == "active":
            base = base.where(StorageLedger.storage_state == StorageState.ACTIVE)
            count_base = count_base.where(StorageLedger.storage_state == StorageState.ACTIVE)
        elif status == "released":
            base = base.where(StorageLedger.storage_state == StorageState.DELETED)
            count_base = count_base.where(StorageLedger.storage_state == StorageState.DELETED)

        total = (await session.execute(count_base)).scalar_one()
        items_result = await session.execute(
            base.order_by(StorageLedger.allocated_at.desc()).limit(limit).offset(offset)
        )
        return list(items_result.scalars().all()), total

    async def list_compute_grants(self, session: AsyncSession, user_id: str) -> list[ComputeGrant]:
        """Return all ComputeGrants for a user, newest first."""
        result = await session.execute(
            select(ComputeGrant).where(ComputeGrant.user_id == user_id).order_by(ComputeGrant.granted_at.desc())
        )
        return list(result.scalars().all())

    async def list_storage_quota_grants(self, session: AsyncSession, user_id: str) -> list[StorageQuotaGrant]:
        """Return all StorageQuotaGrants for a user, newest first."""
        result = await session.execute(
            select(StorageQuotaGrant)
            .where(StorageQuotaGrant.user_id == user_id)
            .order_by(StorageQuotaGrant.granted_at.desc())
        )
        return list(result.scalars().all())

    # ═══════════════════════════════════════════════════════
    #  Grant Management  (F26)
    # ═══════════════════════════════════════════════════════

    async def create_compute_grant(
        self,
        session: AsyncSession,
        user_id: str,
        amount: Decimal,
        grant_type: str,
        *,
        granted_by: str | None = None,
        reason: str | None = None,
        campaign_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> ComputeGrant:
        """Create a new ComputeGrant (consumable compute credits)."""
        now = utc_now()
        grant = ComputeGrant(
            user_id=user_id,
            grant_type=grant_type,
            campaign_id=campaign_id,
            original_amount=amount,
            remaining_amount=amount,
            reason=reason,
            granted_by=granted_by,
            granted_at=now,
            expires_at=expires_at,
        )
        session.add(grant)
        await session.flush()
        return grant

    async def create_storage_quota_grant(
        self,
        session: AsyncSession,
        user_id: str,
        size_gib: int,
        grant_type: str,
        *,
        granted_by: str | None = None,
        reason: str | None = None,
        campaign_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> StorageQuotaGrant:
        """Create a new StorageQuotaGrant (capacity entitlement addon)."""
        now = utc_now()
        grant = StorageQuotaGrant(
            user_id=user_id,
            grant_type=grant_type,
            campaign_id=campaign_id,
            size_gib=size_gib,
            reason=reason,
            granted_by=granted_by,
            granted_at=now,
            expires_at=expires_at,
        )
        session.add(grant)
        await session.flush()
        return grant

    # ═══════════════════════════════════════════════════════
    #  Tier Template Management  (F25–F26)
    # ═══════════════════════════════════════════════════════

    async def list_tier_templates(self, session: AsyncSession) -> list[TierTemplate]:
        """Return all active TierTemplates."""
        result = await session.execute(
            select(TierTemplate)
            .where(TierTemplate.is_active.is_(True))
            .order_by(TierTemplate.compute_units_monthly.asc())
        )
        return list(result.scalars().all())

    async def update_tier_template(
        self,
        session: AsyncSession,
        tier_name: str,
        updates: dict,
        *,
        apply_to_existing: bool = False,
    ) -> tuple[TierTemplate, int]:
        """Update a TierTemplate and optionally propagate to existing users.

        Returns (updated_template, users_affected_count).
        """
        template = await self._get_tier_template(session, tier_name)
        now = utc_now()

        updatable_fields = {
            "compute_units_monthly",
            "storage_capacity_gib",
            "max_concurrent_running",
            "max_sandbox_duration_seconds",
            "allowed_templates",
            "grace_period_seconds",
        }
        for key, value in updates.items():
            if key in updatable_fields:
                setattr(template, key, value)
        template.gmt_updated = now
        session.add(template)

        users_affected = 0
        if apply_to_existing:
            result = await session.execute(select(UserPlan).where(UserPlan.tier == tier_name))
            plans = result.scalars().all()
            field_map = {
                "compute_units_monthly": "compute_units_monthly_limit",
                "storage_capacity_gib": "storage_capacity_limit_gib",
                "max_concurrent_running": "max_concurrent_running",
                "max_sandbox_duration_seconds": "max_sandbox_duration_seconds",
                "allowed_templates": "allowed_templates",
                "grace_period_seconds": "grace_period_seconds",
            }
            updated_tmpl_fields = set(updates.keys()) & set(field_map.keys())
            for plan in plans:
                user_overrides = plan.overrides or {}
                changed = False
                for tmpl_field in updated_tmpl_fields:
                    plan_field = field_map[tmpl_field]
                    if plan_field not in user_overrides:
                        setattr(plan, plan_field, getattr(template, tmpl_field))
                        changed = True
                if changed:
                    plan.gmt_updated = now
                    session.add(plan)
                    users_affected += 1

        await session.flush()
        return template, users_affected

    # ═══════════════════════════════════════════════════════
    #  Internal Helpers
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def apply_overrides(plan: UserPlan, overrides: dict) -> None:
        """Apply admin override values to a UserPlan, validating keys first."""
        for key in overrides:
            if key not in ALLOWED_PLAN_OVERRIDES:
                raise ValidationError(
                    f"Invalid override key: '{key}'. Allowed keys: {', '.join(sorted(ALLOWED_PLAN_OVERRIDES))}"
                )
        for key, value in overrides.items():
            setattr(plan, key, value)
