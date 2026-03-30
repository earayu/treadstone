from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="StorageUsage")


@_attrs_define
class StorageUsage:
    """
    Attributes:
        gib_hours (float):
        current_used_gib (int):
        total_quota_gib (int):
        available_gib (int):
        unit (str | Unset):  Default: 'GiB'.
    """

    gib_hours: float
    current_used_gib: int
    total_quota_gib: int
    available_gib: int
    unit: str | Unset = "GiB"
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        gib_hours = self.gib_hours

        current_used_gib = self.current_used_gib

        total_quota_gib = self.total_quota_gib

        available_gib = self.available_gib

        unit = self.unit

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "gib_hours": gib_hours,
                "current_used_gib": current_used_gib,
                "total_quota_gib": total_quota_gib,
                "available_gib": available_gib,
            }
        )
        if unit is not UNSET:
            field_dict["unit"] = unit

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        gib_hours = d.pop("gib_hours")

        current_used_gib = d.pop("current_used_gib")

        total_quota_gib = d.pop("total_quota_gib")

        available_gib = d.pop("available_gib")

        unit = d.pop("unit", UNSET)

        storage_usage = cls(
            gib_hours=gib_hours,
            current_used_gib=current_used_gib,
            total_quota_gib=total_quota_gib,
            available_gib=available_gib,
            unit=unit,
        )

        storage_usage.additional_properties = d
        return storage_usage

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
