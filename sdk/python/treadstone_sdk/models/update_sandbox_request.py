from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.update_sandbox_request_labels_type_0 import UpdateSandboxRequestLabelsType0


T = TypeVar("T", bound="UpdateSandboxRequest")


@_attrs_define
class UpdateSandboxRequest:
    """Partial update for sandbox metadata (control plane). Immutable fields: template, persist, storage.

    Attributes:
        name (None | str | Unset): Optional custom sandbox name. Sandbox name must be 1-55 characters of lowercase
            letters, numbers, or hyphens, and must start and end with a letter or number. Sandbox names only need to be
            unique for the current user.
        labels (None | Unset | UpdateSandboxRequestLabelsType0): Replace sandbox labels entirely when set.
        auto_stop_interval (int | None | Unset): Minutes of inactivity before auto-stop. 0 means never.
        auto_delete_interval (int | None | Unset): Minutes after stop before auto-delete. -1 disables auto-delete.
    """

    name: None | str | Unset = UNSET
    labels: None | Unset | UpdateSandboxRequestLabelsType0 = UNSET
    auto_stop_interval: int | None | Unset = UNSET
    auto_delete_interval: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.update_sandbox_request_labels_type_0 import UpdateSandboxRequestLabelsType0

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        labels: dict[str, Any] | None | Unset
        if isinstance(self.labels, Unset):
            labels = UNSET
        elif isinstance(self.labels, UpdateSandboxRequestLabelsType0):
            labels = self.labels.to_dict()
        else:
            labels = self.labels

        auto_stop_interval: int | None | Unset
        if isinstance(self.auto_stop_interval, Unset):
            auto_stop_interval = UNSET
        else:
            auto_stop_interval = self.auto_stop_interval

        auto_delete_interval: int | None | Unset
        if isinstance(self.auto_delete_interval, Unset):
            auto_delete_interval = UNSET
        else:
            auto_delete_interval = self.auto_delete_interval

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if labels is not UNSET:
            field_dict["labels"] = labels
        if auto_stop_interval is not UNSET:
            field_dict["auto_stop_interval"] = auto_stop_interval
        if auto_delete_interval is not UNSET:
            field_dict["auto_delete_interval"] = auto_delete_interval

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.update_sandbox_request_labels_type_0 import UpdateSandboxRequestLabelsType0

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_labels(data: object) -> None | Unset | UpdateSandboxRequestLabelsType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                labels_type_0 = UpdateSandboxRequestLabelsType0.from_dict(data)

                return labels_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UpdateSandboxRequestLabelsType0, data)

        labels = _parse_labels(d.pop("labels", UNSET))

        def _parse_auto_stop_interval(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        auto_stop_interval = _parse_auto_stop_interval(d.pop("auto_stop_interval", UNSET))

        def _parse_auto_delete_interval(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        auto_delete_interval = _parse_auto_delete_interval(d.pop("auto_delete_interval", UNSET))

        update_sandbox_request = cls(
            name=name,
            labels=labels,
            auto_stop_interval=auto_stop_interval,
            auto_delete_interval=auto_delete_interval,
        )

        update_sandbox_request.additional_properties = d
        return update_sandbox_request

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
