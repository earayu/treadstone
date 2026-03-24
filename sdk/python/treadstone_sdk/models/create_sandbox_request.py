from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_sandbox_request_labels import CreateSandboxRequestLabels


T = TypeVar("T", bound="CreateSandboxRequest")


@_attrs_define
class CreateSandboxRequest:
    """
    Attributes:
        template (str):
        name (None | str | Unset): Optional custom sandbox name. Sandbox name must be 1-55 characters of lowercase
            letters, numbers, or hyphens, and must start and end with a letter or number. This keeps browser URLs like
            `sandbox-{name}.treadstone-ai.dev` within DNS label limits.
        labels (CreateSandboxRequestLabels | Unset):
        auto_stop_interval (int | Unset): Minutes of inactivity before the sandbox is automatically stopped. Default:
            15.
        auto_delete_interval (int | Unset): Minutes after stop before the sandbox is automatically deleted. -1 disables
            auto-delete. Default: -1.
        persist (bool | Unset):  Default: False.
        storage_size (None | str | Unset): Persistent volume size.
    """

    template: str
    name: None | str | Unset = UNSET
    labels: CreateSandboxRequestLabels | Unset = UNSET
    auto_stop_interval: int | Unset = 15
    auto_delete_interval: int | Unset = -1
    persist: bool | Unset = False
    storage_size: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        template = self.template

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        labels: dict[str, Any] | Unset = UNSET
        if not isinstance(self.labels, Unset):
            labels = self.labels.to_dict()

        auto_stop_interval = self.auto_stop_interval

        auto_delete_interval = self.auto_delete_interval

        persist = self.persist

        storage_size: None | str | Unset
        if isinstance(self.storage_size, Unset):
            storage_size = UNSET
        else:
            storage_size = self.storage_size

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "template": template,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name
        if labels is not UNSET:
            field_dict["labels"] = labels
        if auto_stop_interval is not UNSET:
            field_dict["auto_stop_interval"] = auto_stop_interval
        if auto_delete_interval is not UNSET:
            field_dict["auto_delete_interval"] = auto_delete_interval
        if persist is not UNSET:
            field_dict["persist"] = persist
        if storage_size is not UNSET:
            field_dict["storage_size"] = storage_size

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.create_sandbox_request_labels import CreateSandboxRequestLabels

        d = dict(src_dict)
        template = d.pop("template")

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        _labels = d.pop("labels", UNSET)
        labels: CreateSandboxRequestLabels | Unset
        if isinstance(_labels, Unset):
            labels = UNSET
        else:
            labels = CreateSandboxRequestLabels.from_dict(_labels)

        auto_stop_interval = d.pop("auto_stop_interval", UNSET)

        auto_delete_interval = d.pop("auto_delete_interval", UNSET)

        persist = d.pop("persist", UNSET)

        def _parse_storage_size(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        storage_size = _parse_storage_size(d.pop("storage_size", UNSET))

        create_sandbox_request = cls(
            template=template,
            name=name,
            labels=labels,
            auto_stop_interval=auto_stop_interval,
            auto_delete_interval=auto_delete_interval,
            persist=persist,
            storage_size=storage_size,
        )

        create_sandbox_request.additional_properties = d
        return create_sandbox_request

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
