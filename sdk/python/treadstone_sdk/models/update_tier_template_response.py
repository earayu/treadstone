from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="UpdateTierTemplateResponse")


@_attrs_define
class UpdateTierTemplateResponse:
    """
    Attributes:
        tier (str):
        compute_units_monthly (float):
        storage_capacity_gib (int):
        max_concurrent_running (int):
        max_sandbox_duration_seconds (int):
        allowed_templates (list[str]):
        grace_period_seconds (int):
        is_active (bool):
        created_at (str):
        updated_at (str):
        users_affected (int):
    """

    tier: str
    compute_units_monthly: float
    storage_capacity_gib: int
    max_concurrent_running: int
    max_sandbox_duration_seconds: int
    allowed_templates: list[str]
    grace_period_seconds: int
    is_active: bool
    created_at: str
    updated_at: str
    users_affected: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        tier = self.tier

        compute_units_monthly = self.compute_units_monthly

        storage_capacity_gib = self.storage_capacity_gib

        max_concurrent_running = self.max_concurrent_running

        max_sandbox_duration_seconds = self.max_sandbox_duration_seconds

        allowed_templates = self.allowed_templates

        grace_period_seconds = self.grace_period_seconds

        is_active = self.is_active

        created_at = self.created_at

        updated_at = self.updated_at

        users_affected = self.users_affected

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "tier": tier,
                "compute_units_monthly": compute_units_monthly,
                "storage_capacity_gib": storage_capacity_gib,
                "max_concurrent_running": max_concurrent_running,
                "max_sandbox_duration_seconds": max_sandbox_duration_seconds,
                "allowed_templates": allowed_templates,
                "grace_period_seconds": grace_period_seconds,
                "is_active": is_active,
                "created_at": created_at,
                "updated_at": updated_at,
                "users_affected": users_affected,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        tier = d.pop("tier")

        compute_units_monthly = d.pop("compute_units_monthly")

        storage_capacity_gib = d.pop("storage_capacity_gib")

        max_concurrent_running = d.pop("max_concurrent_running")

        max_sandbox_duration_seconds = d.pop("max_sandbox_duration_seconds")

        allowed_templates = cast(list[str], d.pop("allowed_templates"))

        grace_period_seconds = d.pop("grace_period_seconds")

        is_active = d.pop("is_active")

        created_at = d.pop("created_at")

        updated_at = d.pop("updated_at")

        users_affected = d.pop("users_affected")

        update_tier_template_response = cls(
            tier=tier,
            compute_units_monthly=compute_units_monthly,
            storage_capacity_gib=storage_capacity_gib,
            max_concurrent_running=max_concurrent_running,
            max_sandbox_duration_seconds=max_sandbox_duration_seconds,
            allowed_templates=allowed_templates,
            grace_period_seconds=grace_period_seconds,
            is_active=is_active,
            created_at=created_at,
            updated_at=updated_at,
            users_affected=users_affected,
        )

        update_tier_template_response.additional_properties = d
        return update_tier_template_response

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
