from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.batch_grant_result_item import BatchGrantResultItem


T = TypeVar("T", bound="BatchGrantResponse")


@_attrs_define
class BatchGrantResponse:
    """
    Attributes:
        total_requested (int):
        succeeded (int):
        failed (int):
        results (list[BatchGrantResultItem]):
    """

    total_requested: int
    succeeded: int
    failed: int
    results: list[BatchGrantResultItem]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        total_requested = self.total_requested

        succeeded = self.succeeded

        failed = self.failed

        results = []
        for results_item_data in self.results:
            results_item = results_item_data.to_dict()
            results.append(results_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "total_requested": total_requested,
                "succeeded": succeeded,
                "failed": failed,
                "results": results,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.batch_grant_result_item import BatchGrantResultItem

        d = dict(src_dict)
        total_requested = d.pop("total_requested")

        succeeded = d.pop("succeeded")

        failed = d.pop("failed")

        results = []
        _results = d.pop("results")
        for results_item_data in _results:
            results_item = BatchGrantResultItem.from_dict(results_item_data)

            results.append(results_item)

        batch_grant_response = cls(
            total_requested=total_requested,
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

        batch_grant_response.additional_properties = d
        return batch_grant_response

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
