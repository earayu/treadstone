from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

T = TypeVar("T", bound="SandboxWebLinkResponse")


@_attrs_define
class SandboxWebLinkResponse:
    """
    Attributes:
        web_url (str):
        open_link (str):
        expires_at (datetime.datetime):
    """

    web_url: str
    open_link: str
    expires_at: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        web_url = self.web_url

        open_link = self.open_link

        expires_at = self.expires_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "web_url": web_url,
                "open_link": open_link,
                "expires_at": expires_at,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        web_url = d.pop("web_url")

        open_link = d.pop("open_link")

        expires_at = isoparse(d.pop("expires_at"))

        sandbox_web_link_response = cls(
            web_url=web_url,
            open_link=open_link,
            expires_at=expires_at,
        )

        sandbox_web_link_response.additional_properties = d
        return sandbox_web_link_response

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
