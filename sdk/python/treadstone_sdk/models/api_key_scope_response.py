from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.api_key_data_plane_scope_response import ApiKeyDataPlaneScopeResponse


T = TypeVar("T", bound="ApiKeyScopeResponse")


@_attrs_define
class ApiKeyScopeResponse:
    """
    Attributes:
        control_plane (bool):
        data_plane (ApiKeyDataPlaneScopeResponse):
    """

    control_plane: bool
    data_plane: ApiKeyDataPlaneScopeResponse
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        control_plane = self.control_plane

        data_plane = self.data_plane.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "control_plane": control_plane,
                "data_plane": data_plane,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.api_key_data_plane_scope_response import ApiKeyDataPlaneScopeResponse

        d = dict(src_dict)
        control_plane = d.pop("control_plane")

        data_plane = ApiKeyDataPlaneScopeResponse.from_dict(d.pop("data_plane"))

        api_key_scope_response = cls(
            control_plane=control_plane,
            data_plane=data_plane,
        )

        api_key_scope_response.additional_properties = d
        return api_key_scope_response

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
