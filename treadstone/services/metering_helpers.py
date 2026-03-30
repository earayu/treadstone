"""Metering helper functions — Compute Unit rate calculation, storage size parsing, and shared data types."""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from treadstone.core.errors import BadRequestError

logger = logging.getLogger(__name__)

TEMPLATE_SPECS: dict[str, dict[str, Decimal]] = {
    "aio-sandbox-tiny": {"vcpu": Decimal("0.25"), "memory_gib": Decimal("1")},
    "aio-sandbox-small": {"vcpu": Decimal("0.5"), "memory_gib": Decimal("2")},
    "aio-sandbox-medium": {"vcpu": Decimal("1"), "memory_gib": Decimal("4")},
    "aio-sandbox-large": {"vcpu": Decimal("2"), "memory_gib": Decimal("8")},
    "aio-sandbox-xlarge": {"vcpu": Decimal("4"), "memory_gib": Decimal("16")},
}

# Weights for the additive Compute Unit formula:
#   CU/hour = CU_VCPU_WEIGHT * vCPU + CU_MEMORY_WEIGHT * memory_GiB
# Reference: 1 CU/hour = 1 vCPU + 4 GiB  →  weights = (0.5, 0.125).
# All public templates use a strict 1:4 (vCPU:GiB) ratio so CU/h = vCPU.
CU_VCPU_WEIGHT: Decimal = Decimal("0.5")
CU_MEMORY_WEIGHT: Decimal = Decimal("0.125")

_template_specs_cache: dict[str, dict[str, Decimal]] = {}


def _resolve_spec(template: str) -> dict[str, Decimal] | None:
    """Look up template spec from K8s-synced cache first, then static fallback."""
    return _template_specs_cache.get(template) or TEMPLATE_SPECS.get(template)


def get_template_resource_spec(template: str) -> tuple[Decimal, Decimal]:
    """Return (vcpu_request, memory_gib_request) for the given sandbox template.

    Checks the K8s-synced runtime cache first, falls back to static TEMPLATE_SPECS.
    Raises BadRequestError for unknown templates.
    """
    spec = _resolve_spec(template)
    if spec is None:
        raise BadRequestError(f"Unknown sandbox template: {template}")
    return spec["vcpu"], spec["memory_gib"]


def calculate_cu_rate(template: str) -> Decimal:
    """Return the Compute Unit rate (CU/hour) for the given sandbox template.

    Formula: CU = CU_VCPU_WEIGHT * vCPU + CU_MEMORY_WEIGHT * memory_GiB
    Checks the K8s-synced runtime cache first, falls back to static TEMPLATE_SPECS.
    """
    spec = _resolve_spec(template)
    if spec is None:
        raise BadRequestError(f"Unknown sandbox template: {template}")
    return CU_VCPU_WEIGHT * spec["vcpu"] + CU_MEMORY_WEIGHT * spec["memory_gib"]


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


def _parse_k8s_cpu(value: str) -> Decimal:
    """Convert K8s CPU string (e.g. '250m', '1', '2') to vCPU Decimal."""
    if not value:
        return Decimal("0")
    if value.endswith("m"):
        return Decimal(value[:-1]) / Decimal("1000")
    return Decimal(value)


def _parse_k8s_memory_gib(value: str) -> Decimal:
    """Convert K8s memory string (e.g. '512Mi', '1Gi', '4096Mi') to GiB Decimal."""
    if not value:
        return Decimal("0")
    if value.endswith("Gi"):
        return Decimal(value[:-2])
    if value.endswith("Mi"):
        return Decimal(value[:-2]) / Decimal("1024")
    if value.endswith("Ki"):
        return Decimal(value[:-2]) / Decimal("1048576")
    return Decimal(value) / Decimal("1073741824")


def sync_template_specs_from_k8s(k8s_templates: list[dict]) -> int:
    """Build the runtime template specs cache from K8s SandboxTemplate resource specs.

    Each entry in *k8s_templates* uses the parsed format from ``k8s_client``.
    Returns the number of templates cached.
    """
    global _template_specs_cache
    new_cache: dict[str, dict[str, Decimal]] = {}
    for t in k8s_templates:
        rs = t.get("resource_spec", {})
        vcpu = _parse_k8s_cpu(rs.get("cpu", ""))
        mem = _parse_k8s_memory_gib(rs.get("memory", ""))
        if vcpu > 0 and mem > 0:
            new_cache[t["name"]] = {"vcpu": vcpu, "memory_gib": mem}
    _template_specs_cache = new_cache
    logger.info("Synced %d template specs from K8s into runtime cache", len(new_cache))
    return len(new_cache)


def validate_template_specs(k8s_templates: list[dict]) -> list[str]:
    """Compare TEMPLATE_SPECS against actual K8s SandboxTemplate resource specs.

    Each entry in *k8s_templates* uses the parsed format from ``k8s_client``:
    ``{"name": "...", "resource_spec": {"cpu": "250m", "memory": "512Mi"}, ...}``.

    Returns a list of human-readable warning strings for any drift detected;
    empty list means all specs match.
    """
    warnings: list[str] = []
    k8s_map = {t["name"]: t for t in k8s_templates}

    for name, spec in TEMPLATE_SPECS.items():
        k8s = k8s_map.get(name)
        if k8s is None:
            warnings.append(f"TEMPLATE_SPECS has '{name}' but no matching K8s SandboxTemplate found")
            continue
        rs = k8s.get("resource_spec", {})
        k8s_vcpu = _parse_k8s_cpu(rs.get("cpu", ""))
        k8s_mem = _parse_k8s_memory_gib(rs.get("memory", ""))
        if spec["vcpu"] != k8s_vcpu:
            warnings.append(f"Template '{name}' vCPU drift: metering={spec['vcpu']} vs K8s={k8s_vcpu}")
        if spec["memory_gib"] != k8s_mem:
            warnings.append(f"Template '{name}' memory drift: metering={spec['memory_gib']}GiB vs K8s={k8s_mem}GiB")

    for name in k8s_map:
        if name not in TEMPLATE_SPECS:
            warnings.append(f"K8s SandboxTemplate '{name}' has no entry in TEMPLATE_SPECS")

    for w in warnings:
        logger.warning("Template spec validation: %s", w)

    return warnings


@dataclass(frozen=True)
class ConsumeResult:
    """Result of a dual-pool credit consumption operation."""

    monthly: Decimal
    extra: Decimal
    shortfall: Decimal
