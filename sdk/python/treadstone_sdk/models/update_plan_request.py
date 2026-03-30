from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.update_plan_request_overrides_type_0 import UpdatePlanRequestOverridesType0


T = TypeVar("T", bound="UpdatePlanRequest")


@_attrs_define
class UpdatePlanRequest:
    """
    Attributes:
        tier (None | str | Unset):
        overrides (None | Unset | UpdatePlanRequestOverridesType0):
    """

    tier: None | str | Unset = UNSET
    overrides: None | Unset | UpdatePlanRequestOverridesType0 = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.update_plan_request_overrides_type_0 import UpdatePlanRequestOverridesType0

        tier: None | str | Unset
        if isinstance(self.tier, Unset):
            tier = UNSET
        else:
            tier = self.tier

        overrides: dict[str, Any] | None | Unset
        if isinstance(self.overrides, Unset):
            overrides = UNSET
        elif isinstance(self.overrides, UpdatePlanRequestOverridesType0):
            overrides = self.overrides.to_dict()
        else:
            overrides = self.overrides

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if tier is not UNSET:
            field_dict["tier"] = tier
        if overrides is not UNSET:
            field_dict["overrides"] = overrides

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.update_plan_request_overrides_type_0 import UpdatePlanRequestOverridesType0

        d = dict(src_dict)

        def _parse_tier(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        tier = _parse_tier(d.pop("tier", UNSET))

        def _parse_overrides(data: object) -> None | Unset | UpdatePlanRequestOverridesType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                overrides_type_0 = UpdatePlanRequestOverridesType0.from_dict(data)

                return overrides_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UpdatePlanRequestOverridesType0, data)

        overrides = _parse_overrides(d.pop("overrides", UNSET))

        update_plan_request = cls(
            tier=tier,
            overrides=overrides,
        )

        update_plan_request.additional_properties = d
        return update_plan_request

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
