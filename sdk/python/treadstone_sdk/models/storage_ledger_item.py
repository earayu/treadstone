from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="StorageLedgerItem")


@_attrs_define
class StorageLedgerItem:
    """
    Attributes:
        id (str):
        size_gib (int):
        storage_state (str):
        allocated_at (str):
        gib_hours_consumed (float):
        last_metered_at (str):
        sandbox_id (None | str | Unset):
        released_at (None | str | Unset):
    """

    id: str
    size_gib: int
    storage_state: str
    allocated_at: str
    gib_hours_consumed: float
    last_metered_at: str
    sandbox_id: None | str | Unset = UNSET
    released_at: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        size_gib = self.size_gib

        storage_state = self.storage_state

        allocated_at = self.allocated_at

        gib_hours_consumed = self.gib_hours_consumed

        last_metered_at = self.last_metered_at

        sandbox_id: None | str | Unset
        if isinstance(self.sandbox_id, Unset):
            sandbox_id = UNSET
        else:
            sandbox_id = self.sandbox_id

        released_at: None | str | Unset
        if isinstance(self.released_at, Unset):
            released_at = UNSET
        else:
            released_at = self.released_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "size_gib": size_gib,
                "storage_state": storage_state,
                "allocated_at": allocated_at,
                "gib_hours_consumed": gib_hours_consumed,
                "last_metered_at": last_metered_at,
            }
        )
        if sandbox_id is not UNSET:
            field_dict["sandbox_id"] = sandbox_id
        if released_at is not UNSET:
            field_dict["released_at"] = released_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        size_gib = d.pop("size_gib")

        storage_state = d.pop("storage_state")

        allocated_at = d.pop("allocated_at")

        gib_hours_consumed = d.pop("gib_hours_consumed")

        last_metered_at = d.pop("last_metered_at")

        def _parse_sandbox_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        sandbox_id = _parse_sandbox_id(d.pop("sandbox_id", UNSET))

        def _parse_released_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        released_at = _parse_released_at(d.pop("released_at", UNSET))

        storage_ledger_item = cls(
            id=id,
            size_gib=size_gib,
            storage_state=storage_state,
            allocated_at=allocated_at,
            gib_hours_consumed=gib_hours_consumed,
            last_metered_at=last_metered_at,
            sandbox_id=sandbox_id,
            released_at=released_at,
        )

        storage_ledger_item.additional_properties = d
        return storage_ledger_item

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
