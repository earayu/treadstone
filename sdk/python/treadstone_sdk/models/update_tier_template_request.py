from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UpdateTierTemplateRequest")


@_attrs_define
class UpdateTierTemplateRequest:
    """
    Attributes:
        compute_units_monthly (float | None | Unset):
        storage_capacity_gib (int | None | Unset):
        max_concurrent_running (int | None | Unset):
        max_sandbox_duration_seconds (int | None | Unset):
        allowed_templates (list[str] | None | Unset):
        grace_period_seconds (int | None | Unset):
        apply_to_existing (bool | Unset):  Default: False.
    """

    compute_units_monthly: float | None | Unset = UNSET
    storage_capacity_gib: int | None | Unset = UNSET
    max_concurrent_running: int | None | Unset = UNSET
    max_sandbox_duration_seconds: int | None | Unset = UNSET
    allowed_templates: list[str] | None | Unset = UNSET
    grace_period_seconds: int | None | Unset = UNSET
    apply_to_existing: bool | Unset = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        compute_units_monthly: float | None | Unset
        if isinstance(self.compute_units_monthly, Unset):
            compute_units_monthly = UNSET
        else:
            compute_units_monthly = self.compute_units_monthly

        storage_capacity_gib: int | None | Unset
        if isinstance(self.storage_capacity_gib, Unset):
            storage_capacity_gib = UNSET
        else:
            storage_capacity_gib = self.storage_capacity_gib

        max_concurrent_running: int | None | Unset
        if isinstance(self.max_concurrent_running, Unset):
            max_concurrent_running = UNSET
        else:
            max_concurrent_running = self.max_concurrent_running

        max_sandbox_duration_seconds: int | None | Unset
        if isinstance(self.max_sandbox_duration_seconds, Unset):
            max_sandbox_duration_seconds = UNSET
        else:
            max_sandbox_duration_seconds = self.max_sandbox_duration_seconds

        allowed_templates: list[str] | None | Unset
        if isinstance(self.allowed_templates, Unset):
            allowed_templates = UNSET
        elif isinstance(self.allowed_templates, list):
            allowed_templates = self.allowed_templates

        else:
            allowed_templates = self.allowed_templates

        grace_period_seconds: int | None | Unset
        if isinstance(self.grace_period_seconds, Unset):
            grace_period_seconds = UNSET
        else:
            grace_period_seconds = self.grace_period_seconds

        apply_to_existing = self.apply_to_existing

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if compute_units_monthly is not UNSET:
            field_dict["compute_units_monthly"] = compute_units_monthly
        if storage_capacity_gib is not UNSET:
            field_dict["storage_capacity_gib"] = storage_capacity_gib
        if max_concurrent_running is not UNSET:
            field_dict["max_concurrent_running"] = max_concurrent_running
        if max_sandbox_duration_seconds is not UNSET:
            field_dict["max_sandbox_duration_seconds"] = max_sandbox_duration_seconds
        if allowed_templates is not UNSET:
            field_dict["allowed_templates"] = allowed_templates
        if grace_period_seconds is not UNSET:
            field_dict["grace_period_seconds"] = grace_period_seconds
        if apply_to_existing is not UNSET:
            field_dict["apply_to_existing"] = apply_to_existing

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_compute_units_monthly(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        compute_units_monthly = _parse_compute_units_monthly(d.pop("compute_units_monthly", UNSET))

        def _parse_storage_capacity_gib(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        storage_capacity_gib = _parse_storage_capacity_gib(d.pop("storage_capacity_gib", UNSET))

        def _parse_max_concurrent_running(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_concurrent_running = _parse_max_concurrent_running(d.pop("max_concurrent_running", UNSET))

        def _parse_max_sandbox_duration_seconds(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_sandbox_duration_seconds = _parse_max_sandbox_duration_seconds(d.pop("max_sandbox_duration_seconds", UNSET))

        def _parse_allowed_templates(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                allowed_templates_type_0 = cast(list[str], data)

                return allowed_templates_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        allowed_templates = _parse_allowed_templates(d.pop("allowed_templates", UNSET))

        def _parse_grace_period_seconds(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        grace_period_seconds = _parse_grace_period_seconds(d.pop("grace_period_seconds", UNSET))

        apply_to_existing = d.pop("apply_to_existing", UNSET)

        update_tier_template_request = cls(
            compute_units_monthly=compute_units_monthly,
            storage_capacity_gib=storage_capacity_gib,
            max_concurrent_running=max_concurrent_running,
            max_sandbox_duration_seconds=max_sandbox_duration_seconds,
            allowed_templates=allowed_templates,
            grace_period_seconds=grace_period_seconds,
            apply_to_existing=apply_to_existing,
        )

        update_tier_template_request.additional_properties = d
        return update_tier_template_request

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
