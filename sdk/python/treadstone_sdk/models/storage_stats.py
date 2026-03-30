from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="StorageStats")


@_attrs_define
class StorageStats:
    """
    Attributes:
        total_allocated_gib (float):
        total_consumed_gib_hours (float):
    """

    total_allocated_gib: float
    total_consumed_gib_hours: float
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total_allocated_gib = self.total_allocated_gib

        total_consumed_gib_hours = self.total_consumed_gib_hours

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "total_allocated_gib": total_allocated_gib,
                "total_consumed_gib_hours": total_consumed_gib_hours,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        total_allocated_gib = d.pop("total_allocated_gib")

        total_consumed_gib_hours = d.pop("total_consumed_gib_hours")

        storage_stats = cls(
            total_allocated_gib=total_allocated_gib,
            total_consumed_gib_hours=total_consumed_gib_hours,
        )

        storage_stats.additional_properties = d
        return storage_stats

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
