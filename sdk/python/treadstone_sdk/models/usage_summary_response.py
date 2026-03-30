from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.billing_period import BillingPeriod
    from ..models.compute_usage import ComputeUsage
    from ..models.grace_period_status import GracePeriodStatus
    from ..models.storage_usage import StorageUsage
    from ..models.usage_limits import UsageLimits


T = TypeVar("T", bound="UsageSummaryResponse")


@_attrs_define
class UsageSummaryResponse:
    """
    Attributes:
        tier (str):
        billing_period (BillingPeriod):
        compute (ComputeUsage):
        storage (StorageUsage):
        limits (UsageLimits):
        grace_period (GracePeriodStatus):
    """

    tier: str
    billing_period: BillingPeriod
    compute: ComputeUsage
    storage: StorageUsage
    limits: UsageLimits
    grace_period: GracePeriodStatus
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        tier = self.tier

        billing_period = self.billing_period.to_dict()

        compute = self.compute.to_dict()

        storage = self.storage.to_dict()

        limits = self.limits.to_dict()

        grace_period = self.grace_period.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "tier": tier,
                "billing_period": billing_period,
                "compute": compute,
                "storage": storage,
                "limits": limits,
                "grace_period": grace_period,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.billing_period import BillingPeriod
        from ..models.compute_usage import ComputeUsage
        from ..models.grace_period_status import GracePeriodStatus
        from ..models.storage_usage import StorageUsage
        from ..models.usage_limits import UsageLimits

        d = dict(src_dict)
        tier = d.pop("tier")

        billing_period = BillingPeriod.from_dict(d.pop("billing_period"))

        compute = ComputeUsage.from_dict(d.pop("compute"))

        storage = StorageUsage.from_dict(d.pop("storage"))

        limits = UsageLimits.from_dict(d.pop("limits"))

        grace_period = GracePeriodStatus.from_dict(d.pop("grace_period"))

        usage_summary_response = cls(
            tier=tier,
            billing_period=billing_period,
            compute=compute,
            storage=storage,
            limits=limits,
            grace_period=grace_period,
        )

        usage_summary_response.additional_properties = d
        return usage_summary_response

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
