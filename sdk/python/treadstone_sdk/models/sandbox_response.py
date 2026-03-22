from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.sandbox_response_labels import SandboxResponseLabels
    from ..models.sandbox_urls import SandboxUrls


T = TypeVar("T", bound="SandboxResponse")


@_attrs_define
class SandboxResponse:
    """
    Attributes:
        id (str):
        name (str):
        template (str):
        status (str):
        auto_stop_interval (int): Minutes of inactivity before the sandbox is automatically stopped.
        auto_delete_interval (int): Minutes after stop before auto-delete. -1 means disabled.
        urls (SandboxUrls):
        created_at (datetime.datetime):
        labels (SandboxResponseLabels | Unset):
    """

    id: str
    name: str
    template: str
    status: str
    auto_stop_interval: int
    auto_delete_interval: int
    urls: SandboxUrls
    created_at: datetime.datetime
    labels: SandboxResponseLabels | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        template = self.template

        status = self.status

        auto_stop_interval = self.auto_stop_interval

        auto_delete_interval = self.auto_delete_interval

        urls = self.urls.to_dict()

        created_at = self.created_at.isoformat()

        labels: dict[str, Any] | Unset = UNSET
        if not isinstance(self.labels, Unset):
            labels = self.labels.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "template": template,
                "status": status,
                "auto_stop_interval": auto_stop_interval,
                "auto_delete_interval": auto_delete_interval,
                "urls": urls,
                "created_at": created_at,
            }
        )
        if labels is not UNSET:
            field_dict["labels"] = labels

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.sandbox_response_labels import SandboxResponseLabels
        from ..models.sandbox_urls import SandboxUrls

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        template = d.pop("template")

        status = d.pop("status")

        auto_stop_interval = d.pop("auto_stop_interval")

        auto_delete_interval = d.pop("auto_delete_interval")

        urls = SandboxUrls.from_dict(d.pop("urls"))

        created_at = isoparse(d.pop("created_at"))

        _labels = d.pop("labels", UNSET)
        labels: SandboxResponseLabels | Unset
        if isinstance(_labels, Unset):
            labels = UNSET
        else:
            labels = SandboxResponseLabels.from_dict(_labels)

        sandbox_response = cls(
            id=id,
            name=name,
            template=template,
            status=status,
            auto_stop_interval=auto_stop_interval,
            auto_delete_interval=auto_delete_interval,
            urls=urls,
            created_at=created_at,
            labels=labels,
        )

        sandbox_response.additional_properties = d
        return sandbox_response

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
