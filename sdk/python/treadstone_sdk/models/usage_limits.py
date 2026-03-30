from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UsageLimits")


@_attrs_define
class UsageLimits:
    """
    Attributes:
        max_concurrent_running (int):
        current_running (int):
        max_sandbox_duration_seconds (int): Maximum auto-stop interval in seconds. 0 means unlimited (never).
        allowed_templates (list[str]):
    """

    max_concurrent_running: int
    current_running: int
    max_sandbox_duration_seconds: int
    allowed_templates: list[str]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        max_concurrent_running = self.max_concurrent_running

        current_running = self.current_running

        max_sandbox_duration_seconds = self.max_sandbox_duration_seconds

        allowed_templates = self.allowed_templates

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "max_concurrent_running": max_concurrent_running,
                "current_running": current_running,
                "max_sandbox_duration_seconds": max_sandbox_duration_seconds,
                "allowed_templates": allowed_templates,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        max_concurrent_running = d.pop("max_concurrent_running")

        current_running = d.pop("current_running")

        max_sandbox_duration_seconds = d.pop("max_sandbox_duration_seconds")

        allowed_templates = cast(list[str], d.pop("allowed_templates"))

        usage_limits = cls(
            max_concurrent_running=max_concurrent_running,
            current_running=current_running,
            max_sandbox_duration_seconds=max_sandbox_duration_seconds,
            allowed_templates=allowed_templates,
        )

        usage_limits.additional_properties = d
        return usage_limits

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
