from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ComputeGrantItem")


@_attrs_define
class ComputeGrantItem:
    """
    Attributes:
        id (str):
        grant_type (str):
        original_amount (float):
        remaining_amount (float):
        status (str):
        granted_at (str):
        reason (None | str | Unset):
        granted_by (None | str | Unset):
        campaign_id (None | str | Unset):
        expires_at (None | str | Unset):
    """

    id: str
    grant_type: str
    original_amount: float
    remaining_amount: float
    status: str
    granted_at: str
    reason: None | str | Unset = UNSET
    granted_by: None | str | Unset = UNSET
    campaign_id: None | str | Unset = UNSET
    expires_at: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        grant_type = self.grant_type

        original_amount = self.original_amount

        remaining_amount = self.remaining_amount

        status = self.status

        granted_at = self.granted_at

        reason: None | str | Unset
        if isinstance(self.reason, Unset):
            reason = UNSET
        else:
            reason = self.reason

        granted_by: None | str | Unset
        if isinstance(self.granted_by, Unset):
            granted_by = UNSET
        else:
            granted_by = self.granted_by

        campaign_id: None | str | Unset
        if isinstance(self.campaign_id, Unset):
            campaign_id = UNSET
        else:
            campaign_id = self.campaign_id

        expires_at: None | str | Unset
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        else:
            expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "grant_type": grant_type,
                "original_amount": original_amount,
                "remaining_amount": remaining_amount,
                "status": status,
                "granted_at": granted_at,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason
        if granted_by is not UNSET:
            field_dict["granted_by"] = granted_by
        if campaign_id is not UNSET:
            field_dict["campaign_id"] = campaign_id
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        grant_type = d.pop("grant_type")

        original_amount = d.pop("original_amount")

        remaining_amount = d.pop("remaining_amount")

        status = d.pop("status")

        granted_at = d.pop("granted_at")

        def _parse_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reason = _parse_reason(d.pop("reason", UNSET))

        def _parse_granted_by(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        granted_by = _parse_granted_by(d.pop("granted_by", UNSET))

        def _parse_campaign_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        campaign_id = _parse_campaign_id(d.pop("campaign_id", UNSET))

        def _parse_expires_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

        compute_grant_item = cls(
            id=id,
            grant_type=grant_type,
            original_amount=original_amount,
            remaining_amount=remaining_amount,
            status=status,
            granted_at=granted_at,
            reason=reason,
            granted_by=granted_by,
            campaign_id=campaign_id,
            expires_at=expires_at,
        )

        compute_grant_item.additional_properties = d
        return compute_grant_item

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
