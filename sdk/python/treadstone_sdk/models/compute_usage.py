from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ComputeUsage")


@_attrs_define
class ComputeUsage:
    """
    Attributes:
        compute_unit_hours (float):
        monthly_limit (float):
        monthly_used (float):
        monthly_remaining (float):
        extra_remaining (float):
        total_remaining (float):
        unit (str | Unset):  Default: 'CU-hours'.
    """

    compute_unit_hours: float
    monthly_limit: float
    monthly_used: float
    monthly_remaining: float
    extra_remaining: float
    total_remaining: float
    unit: str | Unset = "CU-hours"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        compute_unit_hours = self.compute_unit_hours

        monthly_limit = self.monthly_limit

        monthly_used = self.monthly_used

        monthly_remaining = self.monthly_remaining

        extra_remaining = self.extra_remaining

        total_remaining = self.total_remaining

        unit = self.unit

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "compute_unit_hours": compute_unit_hours,
                "monthly_limit": monthly_limit,
                "monthly_used": monthly_used,
                "monthly_remaining": monthly_remaining,
                "extra_remaining": extra_remaining,
                "total_remaining": total_remaining,
            }
        )
        if unit is not UNSET:
            field_dict["unit"] = unit

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        compute_unit_hours = d.pop("compute_unit_hours")

        monthly_limit = d.pop("monthly_limit")

        monthly_used = d.pop("monthly_used")

        monthly_remaining = d.pop("monthly_remaining")

        extra_remaining = d.pop("extra_remaining")

        total_remaining = d.pop("total_remaining")

        unit = d.pop("unit", UNSET)

        compute_usage = cls(
            compute_unit_hours=compute_unit_hours,
            monthly_limit=monthly_limit,
            monthly_used=monthly_used,
            monthly_remaining=monthly_remaining,
            extra_remaining=extra_remaining,
            total_remaining=total_remaining,
            unit=unit,
        )

        compute_usage.additional_properties = d
        return compute_usage

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
