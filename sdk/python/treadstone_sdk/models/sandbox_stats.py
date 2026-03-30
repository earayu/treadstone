from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.sandbox_status_count import SandboxStatusCount


T = TypeVar("T", bound="SandboxStats")


@_attrs_define
class SandboxStats:
    """
    Attributes:
        total_created (int):
        currently_running (int):
        status_breakdown (list[SandboxStatusCount]):
    """

    total_created: int
    currently_running: int
    status_breakdown: list[SandboxStatusCount]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total_created = self.total_created

        currently_running = self.currently_running

        status_breakdown = []
        for status_breakdown_item_data in self.status_breakdown:
            status_breakdown_item = status_breakdown_item_data.to_dict()
            status_breakdown.append(status_breakdown_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "total_created": total_created,
                "currently_running": currently_running,
                "status_breakdown": status_breakdown,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.sandbox_status_count import SandboxStatusCount

        d = dict(src_dict)
        total_created = d.pop("total_created")

        currently_running = d.pop("currently_running")

        status_breakdown = []
        _status_breakdown = d.pop("status_breakdown")
        for status_breakdown_item_data in _status_breakdown:
            status_breakdown_item = SandboxStatusCount.from_dict(status_breakdown_item_data)

            status_breakdown.append(status_breakdown_item)

        sandbox_stats = cls(
            total_created=total_created,
            currently_running=currently_running,
            status_breakdown=status_breakdown,
        )

        sandbox_stats.additional_properties = d
        return sandbox_stats

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
