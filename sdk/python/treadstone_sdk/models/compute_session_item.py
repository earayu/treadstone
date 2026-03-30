from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ComputeSessionItem")


@_attrs_define
class ComputeSessionItem:
    """
    Attributes:
        id (str):
        sandbox_id (str):
        template (str):
        vcpu_request (float):
        memory_gib_request (float):
        started_at (str):
        duration_seconds (float):
        compute_unit_hours (float):
        vcpu_hours (float):
        memory_gib_hours (float):
        status (str):
        ended_at (None | str | Unset):
    """

    id: str
    sandbox_id: str
    template: str
    vcpu_request: float
    memory_gib_request: float
    started_at: str
    duration_seconds: float
    compute_unit_hours: float
    vcpu_hours: float
    memory_gib_hours: float
    status: str
    ended_at: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        sandbox_id = self.sandbox_id

        template = self.template

        vcpu_request = self.vcpu_request

        memory_gib_request = self.memory_gib_request

        started_at = self.started_at

        duration_seconds = self.duration_seconds

        compute_unit_hours = self.compute_unit_hours

        vcpu_hours = self.vcpu_hours

        memory_gib_hours = self.memory_gib_hours

        status = self.status

        ended_at: None | str | Unset
        if isinstance(self.ended_at, Unset):
            ended_at = UNSET
        else:
            ended_at = self.ended_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "sandbox_id": sandbox_id,
                "template": template,
                "vcpu_request": vcpu_request,
                "memory_gib_request": memory_gib_request,
                "started_at": started_at,
                "duration_seconds": duration_seconds,
                "compute_unit_hours": compute_unit_hours,
                "vcpu_hours": vcpu_hours,
                "memory_gib_hours": memory_gib_hours,
                "status": status,
            }
        )
        if ended_at is not UNSET:
            field_dict["ended_at"] = ended_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        sandbox_id = d.pop("sandbox_id")

        template = d.pop("template")

        vcpu_request = d.pop("vcpu_request")

        memory_gib_request = d.pop("memory_gib_request")

        started_at = d.pop("started_at")

        duration_seconds = d.pop("duration_seconds")

        compute_unit_hours = d.pop("compute_unit_hours")

        vcpu_hours = d.pop("vcpu_hours")

        memory_gib_hours = d.pop("memory_gib_hours")

        status = d.pop("status")

        def _parse_ended_at(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        ended_at = _parse_ended_at(d.pop("ended_at", UNSET))

        compute_session_item = cls(
            id=id,
            sandbox_id=sandbox_id,
            template=template,
            vcpu_request=vcpu_request,
            memory_gib_request=memory_gib_request,
            started_at=started_at,
            duration_seconds=duration_seconds,
            compute_unit_hours=compute_unit_hours,
            vcpu_hours=vcpu_hours,
            memory_gib_hours=memory_gib_hours,
            status=status,
            ended_at=ended_at,
        )

        compute_session_item.additional_properties = d
        return compute_session_item

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
