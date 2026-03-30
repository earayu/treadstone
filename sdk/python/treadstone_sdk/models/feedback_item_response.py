from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

T = TypeVar("T", bound="FeedbackItemResponse")


@_attrs_define
class FeedbackItemResponse:
    """
    Attributes:
        id (str):
        user_id (str):
        email (str):
        body (str):
        gmt_created (datetime.datetime):
    """

    id: str
    user_id: str
    email: str
    body: str
    gmt_created: datetime.datetime
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        user_id = self.user_id

        email = self.email

        body = self.body

        gmt_created = self.gmt_created.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "user_id": user_id,
                "email": email,
                "body": body,
                "gmt_created": gmt_created,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        user_id = d.pop("user_id")

        email = d.pop("email")

        body = d.pop("body")

        gmt_created = isoparse(d.pop("gmt_created"))

        feedback_item_response = cls(
            id=id,
            user_id=user_id,
            email=email,
            body=body,
            gmt_created=gmt_created,
        )

        feedback_item_response.additional_properties = d
        return feedback_item_response

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
