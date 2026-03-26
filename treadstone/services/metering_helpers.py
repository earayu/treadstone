"""Metering helper functions — credit rate calculation, storage size parsing, and shared data types."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from treadstone.core.errors import BadRequestError

TEMPLATE_SPECS: dict[str, dict[str, Decimal]] = {
    "tiny": {"vcpu": Decimal("0.25"), "memory_gib": Decimal("0.5")},
    "small": {"vcpu": Decimal("0.5"), "memory_gib": Decimal("1")},
    "medium": {"vcpu": Decimal("1"), "memory_gib": Decimal("2")},
    "large": {"vcpu": Decimal("2"), "memory_gib": Decimal("4")},
    "xlarge": {"vcpu": Decimal("4"), "memory_gib": Decimal("8")},
}


def calculate_credit_rate(template: str) -> Decimal:
    """Return the credit rate (credits/hour) for the given sandbox template.

    Formula: max(vCPU_request, memory_GiB_request / 2)
    """
    spec = TEMPLATE_SPECS.get(template)
    if spec is None:
        raise ValueError(f"Unknown template: {template}")
    return max(spec["vcpu"], spec["memory_gib"] / Decimal("2"))


def parse_storage_size_gib(size_str: str) -> int:
    """Convert K8s-style size strings ('5Gi', '10Gi', '1Ti') to integer GiB."""
    if size_str.endswith("Gi"):
        try:
            return int(size_str[:-2])
        except ValueError:
            raise BadRequestError(f"Invalid storage size value: {size_str}")
    if size_str.endswith("Ti"):
        try:
            return int(size_str[:-2]) * 1024
        except ValueError:
            raise BadRequestError(f"Invalid storage size value: {size_str}")
    raise BadRequestError(f"Unsupported storage size format: {size_str}. Use 'Gi' or 'Ti' suffix.")


def compute_period_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) for the billing period containing *now*.

    Billing periods align to natural months: 1st 00:00 UTC → next month 1st 00:00 UTC.
    """
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        period_end = period_start.replace(year=now.year + 1, month=1)
    else:
        period_end = period_start.replace(month=now.month + 1)
    return period_start, period_end


@dataclass(frozen=True)
class ConsumeResult:
    """Result of a dual-pool credit consumption operation."""

    monthly: Decimal
    extra: Decimal
    shortfall: Decimal
