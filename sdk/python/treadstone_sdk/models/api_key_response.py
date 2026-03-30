from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.api_key_scope_response import ApiKeyScopeResponse


T = TypeVar("T", bound="ApiKeyResponse")


@_attrs_define
class ApiKeyResponse:
    """
    Attributes:
        id (str):
        name (str):
        is_enabled (bool):
        key (str):
        created_at (datetime.datetime):
        updated_at (datetime.datetime):
        scope (ApiKeyScopeResponse):
        expires_at (datetime.datetime | None | Unset):
    """

    id: str
    name: str
    is_enabled: bool
    key: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    scope: ApiKeyScopeResponse
    expires_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        is_enabled = self.is_enabled

        key = self.key

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        scope = self.scope.to_dict()

        expires_at: None | str | Unset
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        elif isinstance(self.expires_at, datetime.datetime):
            expires_at = self.expires_at.isoformat()
        else:
            expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "is_enabled": is_enabled,
                "key": key,
                "created_at": created_at,
                "updated_at": updated_at,
                "scope": scope,
            }
        )
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.api_key_scope_response import ApiKeyScopeResponse

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        is_enabled = d.pop("is_enabled")

        key = d.pop("key")

        created_at = isoparse(d.pop("created_at"))

        updated_at = isoparse(d.pop("updated_at"))

        scope = ApiKeyScopeResponse.from_dict(d.pop("scope"))

        def _parse_expires_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                expires_at_type_0 = isoparse(data)

                return expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

        api_key_response = cls(
            id=id,
            name=name,
            is_enabled=is_enabled,
            key=key,
            created_at=created_at,
            updated_at=updated_at,
            scope=scope,
            expires_at=expires_at,
        )

        api_key_response.additional_properties = d
        return api_key_response

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
