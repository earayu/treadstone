from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.user_plan_response_overrides_type_0 import UserPlanResponseOverridesType0


T = TypeVar("T", bound="UserPlanResponse")


@_attrs_define
class UserPlanResponse:
    """
    Attributes:
        id (str):
        user_id (str):
        tier (str):
        compute_units_monthly_limit (float):
        compute_units_monthly_used (float):
        storage_capacity_limit_gib (int):
        max_concurrent_running (int):
        max_sandbox_duration_seconds (int):
        allowed_templates (list[str]):
        grace_period_seconds (int):
        billing_period_start (str):
        billing_period_end (str):
        created_at (str):
        updated_at (str):
        overrides (None | Unset | UserPlanResponseOverridesType0):
        grace_period_started_at (None | str | Unset):
        warning_80_notified_at (None | str | Unset):
        warning_100_notified_at (None | str | Unset):
    """

    id: str
    user_id: str
    tier: str
    compute_units_monthly_limit: float
    compute_units_monthly_used: float
    storage_capacity_limit_gib: int
    max_concurrent_running: int
    max_sandbox_duration_seconds: int
    allowed_templates: list[str]
    grace_period_seconds: int
    billing_period_start: str
    billing_period_end: str
    created_at: str
    updated_at: str
    overrides: None | Unset | UserPlanResponseOverridesType0 = UNSET
    grace_period_started_at: None | str | Unset = UNSET
    warning_80_notified_at: None | str | Unset = UNSET
    warning_100_notified_at: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.user_plan_response_overrides_type_0 import UserPlanResponseOverridesType0

        id = self.id

        user_id = self.user_id

        tier = self.tier

        compute_units_monthly_limit = self.compute_units_monthly_limit

        compute_units_monthly_used = self.compute_units_monthly_used

        storage_capacity_limit_gib = self.storage_capacity_limit_gib

        max_concurrent_running = self.max_concurrent_running

        max_sandbox_duration_seconds = self.max_sandbox_duration_seconds

        allowed_templates = self.allowed_templates

        grace_period_seconds = self.grace_period_seconds

        billing_period_start = self.billing_period_start

        billing_period_end = self.billing_period_end

        created_at = self.created_at

        updated_at = self.updated_at

        overrides: dict[str, Any] | None | Unset
        if isinstance(self.overrides, Unset):
            overrides = UNSET
        elif isinstance(self.overrides, UserPlanResponseOverridesType0):
            overrides = self.overrides.to_dict()
        else:
            overrides = self.overrides

        grace_period_started_at: None | str | Unset
        if isinstance(self.grace_period_started_at, Unset):
            grace_period_started_at = UNSET
        else:
            grace_period_started_at = self.grace_period_started_at

        warning_80_notified_at: None | str | Unset
        if isinstance(self.warning_80_notified_at, Unset):
            warning_80_notified_at = UNSET
        else:
            warning_80_notified_at = self.warning_80_notified_at

        warning_100_notified_at: None | str | Unset
        if isinstance(self.warning_100_notified_at, Unset):
            warning_100_notified_at = UNSET
        else:
            warning_100_notified_at = self.warning_100_notified_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "user_id": user_id,
                "tier": tier,
                "compute_units_monthly_limit": compute_units_monthly_limit,
                "compute_units_monthly_used": compute_units_monthly_used,
                "storage_capacity_limit_gib": storage_capacity_limit_gib,
                "max_concurrent_running": max_concurrent_running,
                "max_sandbox_duration_seconds": max_sandbox_duration_seconds,
                "allowed_templates": allowed_templates,
                "grace_period_seconds": grace_period_seconds,
                "billing_period_start": billing_period_start,
                "billing_period_end": billing_period_end,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )
        if overrides is not UNSET:
            field_dict["overrides"] = overrides
        if grace_period_started_at is not UNSET:
            field_dict["grace_period_started_at"] = grace_period_started_at
        if warning_80_notified_at is not UNSET:
            field_dict["warning_80_notified_at"] = warning_80_notified_at
        if warning_100_notified_at is not UNSET:
            field_dict["warning_100_notified_at"] = warning_100_notified_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user_plan_response_overrides_type_0 import UserPlanResponseOverridesType0

        d = dict(src_dict)
        id = d.pop("id")

        user_id = d.pop("user_id")

        tier = d.pop("tier")

        compute_units_monthly_limit = d.pop("compute_units_monthly_limit")

        compute_units_monthly_used = d.pop("compute_units_monthly_used")

        storage_capacity_limit_gib = d.pop("storage_capacity_limit_gib")

        max_concurrent_running = d.pop("max_concurrent_running")

        max_sandbox_duration_seconds = d.pop("max_sandbox_duration_seconds")

        allowed_templates = cast(list[str], d.pop("allowed_templates"))

        grace_period_seconds = d.pop("grace_period_seconds")

        billing_period_start = d.pop("billing_period_start")

        billing_period_end = d.pop("billing_period_end")

        created_at = d.pop("created_at")

        updated_at = d.pop("updated_at")

        def _parse_overrides(data: object) -> None | Unset | UserPlanResponseOverridesType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                overrides_type_0 = UserPlanResponseOverridesType0.from_dict(data)

                return overrides_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UserPlanResponseOverridesType0, data)

        overrides = _parse_overrides(d.pop("overrides", UNSET))

        def _parse_grace_period_started_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        grace_period_started_at = _parse_grace_period_started_at(d.pop("grace_period_started_at", UNSET))

        def _parse_warning_80_notified_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        warning_80_notified_at = _parse_warning_80_notified_at(d.pop("warning_80_notified_at", UNSET))

        def _parse_warning_100_notified_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        warning_100_notified_at = _parse_warning_100_notified_at(d.pop("warning_100_notified_at", UNSET))

        user_plan_response = cls(
            id=id,
            user_id=user_id,
            tier=tier,
            compute_units_monthly_limit=compute_units_monthly_limit,
            compute_units_monthly_used=compute_units_monthly_used,
            storage_capacity_limit_gib=storage_capacity_limit_gib,
            max_concurrent_running=max_concurrent_running,
            max_sandbox_duration_seconds=max_sandbox_duration_seconds,
            allowed_templates=allowed_templates,
            grace_period_seconds=grace_period_seconds,
            billing_period_start=billing_period_start,
            billing_period_end=billing_period_end,
            created_at=created_at,
            updated_at=updated_at,
            overrides=overrides,
            grace_period_started_at=grace_period_started_at,
            warning_80_notified_at=warning_80_notified_at,
            warning_100_notified_at=warning_100_notified_at,
        )

        user_plan_response.additional_properties = d
        return user_plan_response

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
