from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.compute_grant_item import ComputeGrantItem
    from ..models.storage_quota_grant_item import StorageQuotaGrantItem


T = TypeVar("T", bound="GrantsResponse")


@_attrs_define
class GrantsResponse:
    """
    Attributes:
        compute_grants (list[ComputeGrantItem]):
        storage_quota_grants (list[StorageQuotaGrantItem]):
    """

    compute_grants: list[ComputeGrantItem]
    storage_quota_grants: list[StorageQuotaGrantItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        compute_grants = []
        for compute_grants_item_data in self.compute_grants:
            compute_grants_item = compute_grants_item_data.to_dict()
            compute_grants.append(compute_grants_item)

        storage_quota_grants = []
        for storage_quota_grants_item_data in self.storage_quota_grants:
            storage_quota_grants_item = storage_quota_grants_item_data.to_dict()
            storage_quota_grants.append(storage_quota_grants_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "compute_grants": compute_grants,
                "storage_quota_grants": storage_quota_grants,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.compute_grant_item import ComputeGrantItem
        from ..models.storage_quota_grant_item import StorageQuotaGrantItem

        d = dict(src_dict)
        compute_grants = []
        _compute_grants = d.pop("compute_grants")
        for compute_grants_item_data in _compute_grants:
            compute_grants_item = ComputeGrantItem.from_dict(compute_grants_item_data)

            compute_grants.append(compute_grants_item)

        storage_quota_grants = []
        _storage_quota_grants = d.pop("storage_quota_grants")
        for storage_quota_grants_item_data in _storage_quota_grants:
            storage_quota_grants_item = StorageQuotaGrantItem.from_dict(storage_quota_grants_item_data)

            storage_quota_grants.append(storage_quota_grants_item)

        grants_response = cls(
            compute_grants=compute_grants,
            storage_quota_grants=storage_quota_grants,
        )

        grants_response.additional_properties = d
        return grants_response

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
