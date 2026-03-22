from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.auth_0_config import Auth0Config
    from ..models.authing_config import AuthingConfig
    from ..models.logto_config import LogtoConfig


T = TypeVar("T", bound="AuthConfig")


@_attrs_define
class AuthConfig:
    """
    Attributes:
        type_ (str):
        login_methods (list[str]):
        auth0 (Auth0Config | None | Unset):
        authing (AuthingConfig | None | Unset):
        logto (LogtoConfig | None | Unset):
    """

    type_: str
    login_methods: list[str]
    auth0: Auth0Config | None | Unset = UNSET
    authing: AuthingConfig | None | Unset = UNSET
    logto: LogtoConfig | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.auth_0_config import Auth0Config
        from ..models.authing_config import AuthingConfig
        from ..models.logto_config import LogtoConfig

        type_ = self.type_

        login_methods = self.login_methods

        auth0: dict[str, Any] | None | Unset
        if isinstance(self.auth0, Unset):
            auth0 = UNSET
        elif isinstance(self.auth0, Auth0Config):
            auth0 = self.auth0.to_dict()
        else:
            auth0 = self.auth0

        authing: dict[str, Any] | None | Unset
        if isinstance(self.authing, Unset):
            authing = UNSET
        elif isinstance(self.authing, AuthingConfig):
            authing = self.authing.to_dict()
        else:
            authing = self.authing

        logto: dict[str, Any] | None | Unset
        if isinstance(self.logto, Unset):
            logto = UNSET
        elif isinstance(self.logto, LogtoConfig):
            logto = self.logto.to_dict()
        else:
            logto = self.logto

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
                "login_methods": login_methods,
            }
        )
        if auth0 is not UNSET:
            field_dict["auth0"] = auth0
        if authing is not UNSET:
            field_dict["authing"] = authing
        if logto is not UNSET:
            field_dict["logto"] = logto

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.auth_0_config import Auth0Config
        from ..models.authing_config import AuthingConfig
        from ..models.logto_config import LogtoConfig

        d = dict(src_dict)
        type_ = d.pop("type")

        login_methods = cast(list[str], d.pop("login_methods"))

        def _parse_auth0(data: object) -> Auth0Config | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                auth0_type_0 = Auth0Config.from_dict(data)

                return auth0_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(Auth0Config | None | Unset, data)

        auth0 = _parse_auth0(d.pop("auth0", UNSET))

        def _parse_authing(data: object) -> AuthingConfig | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                authing_type_0 = AuthingConfig.from_dict(data)

                return authing_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(AuthingConfig | None | Unset, data)

        authing = _parse_authing(d.pop("authing", UNSET))

        def _parse_logto(data: object) -> LogtoConfig | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                logto_type_0 = LogtoConfig.from_dict(data)

                return logto_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(LogtoConfig | None | Unset, data)

        logto = _parse_logto(d.pop("logto", UNSET))

        auth_config = cls(
            type_=type_,
            login_methods=login_methods,
            auth0=auth0,
            authing=authing,
            logto=logto,
        )

        auth_config.additional_properties = d
        return auth_config

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
