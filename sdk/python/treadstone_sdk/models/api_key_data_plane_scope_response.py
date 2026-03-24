from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.api_key_data_plane_mode import ApiKeyDataPlaneMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="ApiKeyDataPlaneScopeResponse")


@_attrs_define
class ApiKeyDataPlaneScopeResponse:
    """
    Attributes:
        mode (ApiKeyDataPlaneMode):
        sandbox_ids (list[str] | Unset):
    """

    mode: ApiKeyDataPlaneMode
    sandbox_ids: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        mode = self.mode.value

        sandbox_ids: list[str] | Unset = UNSET
        if not isinstance(self.sandbox_ids, Unset):
            sandbox_ids = self.sandbox_ids

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "mode": mode,
            }
        )
        if sandbox_ids is not UNSET:
            field_dict["sandbox_ids"] = sandbox_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        mode = ApiKeyDataPlaneMode(d.pop("mode"))

        sandbox_ids = cast(list[str], d.pop("sandbox_ids", UNSET))

        api_key_data_plane_scope_response = cls(
            mode=mode,
            sandbox_ids=sandbox_ids,
        )

        api_key_data_plane_scope_response.additional_properties = d
        return api_key_data_plane_scope_response

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
