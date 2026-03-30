from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.role import Role

T = TypeVar("T", bound="RegisterResponse")


@_attrs_define
class RegisterResponse:
    """
    Attributes:
        id (str):
        email (str):
        role (Role):
        is_active (bool):
        is_verified (bool):
        verification_email_sent (bool):
    """

    id: str
    email: str
    role: Role
    is_active: bool
    is_verified: bool
    verification_email_sent: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        email = self.email

        role = self.role.value

        is_active = self.is_active

        is_verified = self.is_verified

        verification_email_sent = self.verification_email_sent

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "email": email,
                "role": role,
                "is_active": is_active,
                "is_verified": is_verified,
                "verification_email_sent": verification_email_sent,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        email = d.pop("email")

        role = Role(d.pop("role"))

        is_active = d.pop("is_active")

        is_verified = d.pop("is_verified")

        verification_email_sent = d.pop("verification_email_sent")

        register_response = cls(
            id=id,
            email=email,
            role=role,
            is_active=is_active,
            is_verified=is_verified,
            verification_email_sent=verification_email_sent,
        )

        register_response.additional_properties = d
        return register_response

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
