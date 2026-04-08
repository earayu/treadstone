from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

T = TypeVar("T", bound="WaitlistApplicationResponse")


@_attrs_define
class WaitlistApplicationResponse:
    """
    Attributes:
        id (str):
        email (str):
        name (str):
        target_tier (str):
        status (str):
        gmt_created (datetime.datetime):
        company (None | str | Unset):
        github_or_portfolio_url (None | str | Unset):
        use_case (None | str | Unset):
        processed_at (datetime.datetime | None | Unset):
    """

    id: str
    email: str
    name: str
    target_tier: str
    status: str
    gmt_created: datetime.datetime
    company: None | str | Unset = UNSET
    github_or_portfolio_url: None | str | Unset = UNSET
    use_case: None | str | Unset = UNSET
    processed_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        email = self.email

        name = self.name

        target_tier = self.target_tier

        status = self.status

        gmt_created = self.gmt_created.isoformat()

        company: None | str | Unset
        if isinstance(self.company, Unset):
            company = UNSET
        else:
            company = self.company

        github_or_portfolio_url: None | str | Unset
        if isinstance(self.github_or_portfolio_url, Unset):
            github_or_portfolio_url = UNSET
        else:
            github_or_portfolio_url = self.github_or_portfolio_url

        use_case: None | str | Unset
        if isinstance(self.use_case, Unset):
            use_case = UNSET
        else:
            use_case = self.use_case

        processed_at: None | str | Unset
        if isinstance(self.processed_at, Unset):
            processed_at = UNSET
        elif isinstance(self.processed_at, datetime.datetime):
            processed_at = self.processed_at.isoformat()
        else:
            processed_at = self.processed_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "email": email,
                "name": name,
                "target_tier": target_tier,
                "status": status,
                "gmt_created": gmt_created,
            }
        )
        if company is not UNSET:
            field_dict["company"] = company
        if github_or_portfolio_url is not UNSET:
            field_dict["github_or_portfolio_url"] = github_or_portfolio_url
        if use_case is not UNSET:
            field_dict["use_case"] = use_case
        if processed_at is not UNSET:
            field_dict["processed_at"] = processed_at

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        email = d.pop("email")

        name = d.pop("name")

        target_tier = d.pop("target_tier")

        status = d.pop("status")

        gmt_created = isoparse(d.pop("gmt_created"))

        def _parse_company(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        company = _parse_company(d.pop("company", UNSET))

        def _parse_github_or_portfolio_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        github_or_portfolio_url = _parse_github_or_portfolio_url(d.pop("github_or_portfolio_url", UNSET))

        def _parse_use_case(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        use_case = _parse_use_case(d.pop("use_case", UNSET))

        def _parse_processed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                processed_at_type_0 = isoparse(data)

                return processed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        processed_at = _parse_processed_at(d.pop("processed_at", UNSET))

        waitlist_application_response = cls(
            id=id,
            email=email,
            name=name,
            target_tier=target_tier,
            status=status,
            gmt_created=gmt_created,
            company=company,
            github_or_portfolio_url=github_or_portfolio_url,
            use_case=use_case,
            processed_at=processed_at,
        )

        waitlist_application_response.additional_properties = d
        return waitlist_application_response

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
