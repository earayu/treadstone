from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.sandbox_detail_response_labels import SandboxDetailResponseLabels
    from ..models.sandbox_storage_response import SandboxStorageResponse
    from ..models.sandbox_urls import SandboxUrls


T = TypeVar("T", bound="SandboxDetailResponse")


@_attrs_define
class SandboxDetailResponse:
    """
    Attributes:
        id (str):
        name (str):
        template (str):
        status (str):
        auto_stop_interval (int): Minutes of inactivity before the sandbox is automatically stopped. 0 means never auto-
            stop.
        auto_delete_interval (int): Minutes after stop before auto-delete. -1 means disabled.
        urls (SandboxUrls):
        created_at (datetime.datetime):
        labels (SandboxDetailResponseLabels | Unset):
        persist (bool | Unset): Whether persistent storage is attached. Default: False.
        storage_size (None | str | Unset): Persistent volume size when persist=true.
        pending_operation (None | str | Unset):
        storage (None | SandboxStorageResponse | Unset):
        image (None | str | Unset):
        status_message (None | str | Unset):
        started_at (datetime.datetime | None | Unset):
        stopped_at (datetime.datetime | None | Unset):
    """

    id: str
    name: str
    template: str
    status: str
    auto_stop_interval: int
    auto_delete_interval: int
    urls: SandboxUrls
    created_at: datetime.datetime
    labels: SandboxDetailResponseLabels | Unset = UNSET
    persist: bool | Unset = False
    storage_size: None | str | Unset = UNSET
    pending_operation: None | str | Unset = UNSET
    storage: None | SandboxStorageResponse | Unset = UNSET
    image: None | str | Unset = UNSET
    status_message: None | str | Unset = UNSET
    started_at: datetime.datetime | None | Unset = UNSET
    stopped_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.sandbox_storage_response import SandboxStorageResponse

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

        persist = self.persist

        storage_size: None | str | Unset
        if isinstance(self.storage_size, Unset):
            storage_size = UNSET
        else:
            storage_size = self.storage_size

        pending_operation: None | str | Unset
        if isinstance(self.pending_operation, Unset):
            pending_operation = UNSET
        else:
            pending_operation = self.pending_operation

        storage: dict[str, Any] | None | Unset
        if isinstance(self.storage, Unset):
            storage = UNSET
        elif isinstance(self.storage, SandboxStorageResponse):
            storage = self.storage.to_dict()
        else:
            storage = self.storage

        image: None | str | Unset
        if isinstance(self.image, Unset):
            image = UNSET
        else:
            image = self.image

        status_message: None | str | Unset
        if isinstance(self.status_message, Unset):
            status_message = UNSET
        else:
            status_message = self.status_message

        started_at: None | str | Unset
        if isinstance(self.started_at, Unset):
            started_at = UNSET
        elif isinstance(self.started_at, datetime.datetime):
            started_at = self.started_at.isoformat()
        else:
            started_at = self.started_at

        stopped_at: None | str | Unset
        if isinstance(self.stopped_at, Unset):
            stopped_at = UNSET
        elif isinstance(self.stopped_at, datetime.datetime):
            stopped_at = self.stopped_at.isoformat()
        else:
            stopped_at = self.stopped_at

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
        if persist is not UNSET:
            field_dict["persist"] = persist
        if storage_size is not UNSET:
            field_dict["storage_size"] = storage_size
        if pending_operation is not UNSET:
            field_dict["pending_operation"] = pending_operation
        if storage is not UNSET:
            field_dict["storage"] = storage
        if image is not UNSET:
            field_dict["image"] = image
        if status_message is not UNSET:
            field_dict["status_message"] = status_message
        if started_at is not UNSET:
            field_dict["started_at"] = started_at
        if stopped_at is not UNSET:
            field_dict["stopped_at"] = stopped_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.sandbox_detail_response_labels import SandboxDetailResponseLabels
        from ..models.sandbox_storage_response import SandboxStorageResponse
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
        labels: SandboxDetailResponseLabels | Unset
        if isinstance(_labels, Unset):
            labels = UNSET
        else:
            labels = SandboxDetailResponseLabels.from_dict(_labels)

        persist = d.pop("persist", UNSET)

        def _parse_storage_size(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        storage_size = _parse_storage_size(d.pop("storage_size", UNSET))

        def _parse_pending_operation(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        pending_operation = _parse_pending_operation(d.pop("pending_operation", UNSET))

        def _parse_storage(data: object) -> None | SandboxStorageResponse | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                storage_type_0 = SandboxStorageResponse.from_dict(data)

                return storage_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | SandboxStorageResponse | Unset, data)

        storage = _parse_storage(d.pop("storage", UNSET))

        def _parse_image(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        image = _parse_image(d.pop("image", UNSET))

        def _parse_status_message(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status_message = _parse_status_message(d.pop("status_message", UNSET))

        def _parse_started_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                started_at_type_0 = isoparse(data)

                return started_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        started_at = _parse_started_at(d.pop("started_at", UNSET))

        def _parse_stopped_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                stopped_at_type_0 = isoparse(data)

                return stopped_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        stopped_at = _parse_stopped_at(d.pop("stopped_at", UNSET))

        sandbox_detail_response = cls(
            id=id,
            name=name,
            template=template,
            status=status,
            auto_stop_interval=auto_stop_interval,
            auto_delete_interval=auto_delete_interval,
            urls=urls,
            created_at=created_at,
            labels=labels,
            persist=persist,
            storage_size=storage_size,
            pending_operation=pending_operation,
            storage=storage,
            image=image,
            status_message=status_message,
            started_at=started_at,
            stopped_at=stopped_at,
        )

        sandbox_detail_response.additional_properties = d
        return sandbox_detail_response

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
