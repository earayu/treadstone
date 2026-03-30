from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role import Role
from ..types import UNSET, Unset

T = TypeVar("T", bound="UserDetailResponse")


@_attrs_define
class UserDetailResponse:
    """
    Attributes:
        id (str):
        email (str):
        role (Role):
        is_active (bool):
        is_verified (bool):
        has_local_password (bool):
        username (None | str | Unset):
    """

    id: str
    email: str
    role: Role
    is_active: bool
    is_verified: bool
    has_local_password: bool
    username: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        email = self.email

        role = self.role.value

        is_active = self.is_active

        is_verified = self.is_verified

        has_local_password = self.has_local_password

        username: None | str | Unset
        if isinstance(self.username, Unset):
            username = UNSET
        else:
            username = self.username

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "email": email,
                "role": role,
                "is_active": is_active,
                "is_verified": is_verified,
                "has_local_password": has_local_password,
            }
        )
        if username is not UNSET:
            field_dict["username"] = username

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        email = d.pop("email")

        role = Role(d.pop("role"))

        is_active = d.pop("is_active")

        is_verified = d.pop("is_verified")

        has_local_password = d.pop("has_local_password")

        def _parse_username(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        username = _parse_username(d.pop("username", UNSET))

        user_detail_response = cls(
            id=id,
            email=email,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            has_local_password=has_local_password,
            username=username,
        )

        user_detail_response.additional_properties = d
        return user_detail_response

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
