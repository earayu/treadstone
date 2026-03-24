from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.api_key_data_plane_scope import ApiKeyDataPlaneScope


T = TypeVar("T", bound="ApiKeyScope")


@_attrs_define
class ApiKeyScope:
    """
    Attributes:
        control_plane (bool | Unset):  Default: True.
        data_plane (ApiKeyDataPlaneScope | Unset):
    """

    control_plane: bool | Unset = True
    data_plane: ApiKeyDataPlaneScope | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        control_plane = self.control_plane

        data_plane: dict[str, Any] | Unset = UNSET
        if not isinstance(self.data_plane, Unset):
            data_plane = self.data_plane.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if control_plane is not UNSET:
            field_dict["control_plane"] = control_plane
        if data_plane is not UNSET:
            field_dict["data_plane"] = data_plane

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.api_key_data_plane_scope import ApiKeyDataPlaneScope

        d = dict(src_dict)
        control_plane = d.pop("control_plane", UNSET)

        _data_plane = d.pop("data_plane", UNSET)
        data_plane: ApiKeyDataPlaneScope | Unset
        if isinstance(_data_plane, Unset):
            data_plane = UNSET
        else:
            data_plane = ApiKeyDataPlaneScope.from_dict(_data_plane)

        api_key_scope = cls(
            control_plane=control_plane,
            data_plane=data_plane,
        )

        api_key_scope.additional_properties = d
        return api_key_scope

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
