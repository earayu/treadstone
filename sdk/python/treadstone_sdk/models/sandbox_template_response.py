from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.resource_spec import ResourceSpec


T = TypeVar("T", bound="SandboxTemplateResponse")


@_attrs_define
class SandboxTemplateResponse:
    """
    Attributes:
        name (str):
        display_name (str):
        description (str):
        image (str):
        resource_spec (ResourceSpec):
    """

    name: str
    display_name: str
    description: str
    image: str
    resource_spec: ResourceSpec
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        display_name = self.display_name

        description = self.description

        image = self.image

        resource_spec = self.resource_spec.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "display_name": display_name,
                "description": description,
                "image": image,
                "resource_spec": resource_spec,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.resource_spec import ResourceSpec

        d = dict(src_dict)
        name = d.pop("name")

        display_name = d.pop("display_name")

        description = d.pop("description")

        image = d.pop("image")

        resource_spec = ResourceSpec.from_dict(d.pop("resource_spec"))

        sandbox_template_response = cls(
            name=name,
            display_name=display_name,
            description=description,
            image=image,
            resource_spec=resource_spec,
        )

        sandbox_template_response.additional_properties = d
        return sandbox_template_response

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
