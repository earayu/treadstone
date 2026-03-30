from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateStorageQuotaGrantRequest")


@_attrs_define
class CreateStorageQuotaGrantRequest:
    """
    Attributes:
        size_gib (int):
        grant_type (str):
        reason (None | str | Unset):
        campaign_id (None | str | Unset):
        expires_at (datetime.datetime | None | Unset):
    """

    size_gib: int
    grant_type: str
    reason: None | str | Unset = UNSET
    campaign_id: None | str | Unset = UNSET
    expires_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        size_gib = self.size_gib

        grant_type = self.grant_type

        reason: None | str | Unset
        if isinstance(self.reason, Unset):
            reason = UNSET
        else:
            reason = self.reason

        campaign_id: None | str | Unset
        if isinstance(self.campaign_id, Unset):
            campaign_id = UNSET
        else:
            campaign_id = self.campaign_id

        expires_at: None | str | Unset
        if isinstance(self.expires_at, Unset):
            expires_at = UNSET
        elif isinstance(self.expires_at, datetime.datetime):
            expires_at = self.expires_at.isoformat()
        else:
            expires_at = self.expires_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "size_gib": size_gib,
                "grant_type": grant_type,
            }
        )
        if reason is not UNSET:
            field_dict["reason"] = reason
        if campaign_id is not UNSET:
            field_dict["campaign_id"] = campaign_id
        if expires_at is not UNSET:
            field_dict["expires_at"] = expires_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        size_gib = d.pop("size_gib")

        grant_type = d.pop("grant_type")

        def _parse_reason(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reason = _parse_reason(d.pop("reason", UNSET))

        def _parse_campaign_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        campaign_id = _parse_campaign_id(d.pop("campaign_id", UNSET))

        def _parse_expires_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                expires_at_type_0 = isoparse(data)

                return expires_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        expires_at = _parse_expires_at(d.pop("expires_at", UNSET))

        create_storage_quota_grant_request = cls(
            size_gib=size_gib,
            grant_type=grant_type,
            reason=reason,
            campaign_id=campaign_id,
            expires_at=expires_at,
        )

        create_storage_quota_grant_request.additional_properties = d
        return create_storage_quota_grant_request

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
