from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.api_key_scope import ApiKeyScope


T = TypeVar("T", bound="UpdateApiKeyRequest")


@_attrs_define
class UpdateApiKeyRequest:
    """
    Attributes:
        name (None | str | Unset):
        is_enabled (bool | None | Unset): Enable or disable the API key.
        expires_in (int | None | Unset): Reset the key lifetime from now in seconds.
        clear_expiration (bool | Unset):  Default: False.
        scope (ApiKeyScope | None | Unset):
    """

    name: None | str | Unset = UNSET
    is_enabled: bool | None | Unset = UNSET
    expires_in: int | None | Unset = UNSET
    clear_expiration: bool | Unset = False
    scope: ApiKeyScope | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.api_key_scope import ApiKeyScope

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        is_enabled: bool | None | Unset
        if isinstance(self.is_enabled, Unset):
            is_enabled = UNSET
        else:
            is_enabled = self.is_enabled

        expires_in: int | None | Unset
        if isinstance(self.expires_in, Unset):
            expires_in = UNSET
        else:
            expires_in = self.expires_in

        clear_expiration = self.clear_expiration

        scope: dict[str, Any] | None | Unset
        if isinstance(self.scope, Unset):
            scope = UNSET
        elif isinstance(self.scope, ApiKeyScope):
            scope = self.scope.to_dict()
        else:
            scope = self.scope

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if is_enabled is not UNSET:
            field_dict["is_enabled"] = is_enabled
        if expires_in is not UNSET:
            field_dict["expires_in"] = expires_in
        if clear_expiration is not UNSET:
            field_dict["clear_expiration"] = clear_expiration
        if scope is not UNSET:
            field_dict["scope"] = scope

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.api_key_scope import ApiKeyScope

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_is_enabled(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        is_enabled = _parse_is_enabled(d.pop("is_enabled", UNSET))

        def _parse_expires_in(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        expires_in = _parse_expires_in(d.pop("expires_in", UNSET))

        clear_expiration = d.pop("clear_expiration", UNSET)

        def _parse_scope(data: object) -> ApiKeyScope | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                scope_type_0 = ApiKeyScope.from_dict(data)

                return scope_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ApiKeyScope | None | Unset, data)

        scope = _parse_scope(d.pop("scope", UNSET))

        update_api_key_request = cls(
            name=name,
            is_enabled=is_enabled,
            expires_in=expires_in,
            clear_expiration=clear_expiration,
            scope=scope,
        )

        update_api_key_request.additional_properties = d
        return update_api_key_request

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
