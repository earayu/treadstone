from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="SandboxStorageResponse")


@_attrs_define
class SandboxStorageResponse:
    """
    Attributes:
        mode (str):
        size (str):
        snapshot_created_at (datetime.datetime | None | Unset):
        zone (None | str | Unset):
    """

    mode: str
    size: str
    snapshot_created_at: datetime.datetime | None | Unset = UNSET
    zone: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        mode = self.mode

        size = self.size

        snapshot_created_at: None | str | Unset
        if isinstance(self.snapshot_created_at, Unset):
            snapshot_created_at = UNSET
        elif isinstance(self.snapshot_created_at, datetime.datetime):
            snapshot_created_at = self.snapshot_created_at.isoformat()
        else:
            snapshot_created_at = self.snapshot_created_at

        zone: None | str | Unset
        if isinstance(self.zone, Unset):
            zone = UNSET
        else:
            zone = self.zone

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "mode": mode,
                "size": size,
            }
        )
        if snapshot_created_at is not UNSET:
            field_dict["snapshot_created_at"] = snapshot_created_at
        if zone is not UNSET:
            field_dict["zone"] = zone

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        mode = d.pop("mode")

        size = d.pop("size")

        def _parse_snapshot_created_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                snapshot_created_at_type_0 = isoparse(data)

                return snapshot_created_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        snapshot_created_at = _parse_snapshot_created_at(d.pop("snapshot_created_at", UNSET))

        def _parse_zone(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        zone = _parse_zone(d.pop("zone", UNSET))

        sandbox_storage_response = cls(
            mode=mode,
            size=size,
            snapshot_created_at=snapshot_created_at,
            zone=zone,
        )

        sandbox_storage_response.additional_properties = d
        return sandbox_storage_response

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
