from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="AuditFilterOptionsResponse")


@_attrs_define
class AuditFilterOptionsResponse:
    """
    Attributes:
        actions (list[str] | Unset):
        target_types (list[str] | Unset):
        results (list[str] | Unset):
    """

    actions: list[str] | Unset = UNSET
    target_types: list[str] | Unset = UNSET
    results: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        actions: list[str] | Unset = UNSET
        if not isinstance(self.actions, Unset):
            actions = self.actions

        target_types: list[str] | Unset = UNSET
        if not isinstance(self.target_types, Unset):
            target_types = self.target_types

        results: list[str] | Unset = UNSET
        if not isinstance(self.results, Unset):
            results = self.results

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if actions is not UNSET:
            field_dict["actions"] = actions
        if target_types is not UNSET:
            field_dict["target_types"] = target_types
        if results is not UNSET:
            field_dict["results"] = results

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        actions = cast(list[str], d.pop("actions", UNSET))

        target_types = cast(list[str], d.pop("target_types", UNSET))

        results = cast(list[str], d.pop("results", UNSET))

        audit_filter_options_response = cls(
            actions=actions,
            target_types=target_types,
            results=results,
        )

        audit_filter_options_response.additional_properties = d
        return audit_filter_options_response

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
