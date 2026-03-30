from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.compute_stats import ComputeStats
    from ..models.sandbox_stats import SandboxStats
    from ..models.storage_stats import StorageStats
    from ..models.user_stats import UserStats


T = TypeVar("T", bound="PlatformStatsResponse")


@_attrs_define
class PlatformStatsResponse:
    """
    Attributes:
        users (UserStats):
        sandboxes (SandboxStats):
        compute (ComputeStats):
        storage (StorageStats):
    """

    users: UserStats
    sandboxes: SandboxStats
    compute: ComputeStats
    storage: StorageStats
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        users = self.users.to_dict()

        sandboxes = self.sandboxes.to_dict()

        compute = self.compute.to_dict()

        storage = self.storage.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "users": users,
                "sandboxes": sandboxes,
                "compute": compute,
                "storage": storage,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.compute_stats import ComputeStats
        from ..models.sandbox_stats import SandboxStats
        from ..models.storage_stats import StorageStats
        from ..models.user_stats import UserStats

        d = dict(src_dict)
        users = UserStats.from_dict(d.pop("users"))

        sandboxes = SandboxStats.from_dict(d.pop("sandboxes"))

        compute = ComputeStats.from_dict(d.pop("compute"))

        storage = StorageStats.from_dict(d.pop("storage"))

        platform_stats_response = cls(
            users=users,
            sandboxes=sandboxes,
            compute=compute,
            storage=storage,
        )

        platform_stats_response.additional_properties = d
        return platform_stats_response

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
