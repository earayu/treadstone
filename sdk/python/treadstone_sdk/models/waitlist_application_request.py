from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="WaitlistApplicationRequest")


@_attrs_define
class WaitlistApplicationRequest:
    """
    Attributes:
        email (str): Applicant email. Does not require an existing account; multiple applications allowed.
        name (str):
        target_tier (str): Target tier: 'pro' or 'ultra'
        company (None | str | Unset):
        github_or_portfolio_url (None | str | Unset): Optional HTTPS URL (GitHub profile, repository, or portfolio).
        use_case (None | str | Unset):
    """

    email: str
    name: str
    target_tier: str
    company: None | str | Unset = UNSET
    github_or_portfolio_url: None | str | Unset = UNSET
    use_case: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        email = self.email

        name = self.name

        target_tier = self.target_tier

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

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "email": email,
                "name": name,
                "target_tier": target_tier,
            }
        )
        if company is not UNSET:
            field_dict["company"] = company
        if github_or_portfolio_url is not UNSET:
            field_dict["github_or_portfolio_url"] = github_or_portfolio_url
        if use_case is not UNSET:
            field_dict["use_case"] = use_case

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        email = d.pop("email")

        name = d.pop("name")

        target_tier = d.pop("target_tier")

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

        waitlist_application_request = cls(
            email=email,
            name=name,
            target_tier=target_tier,
            company=company,
            github_or_portfolio_url=github_or_portfolio_url,
            use_case=use_case,
        )

        waitlist_application_request.additional_properties = d
        return waitlist_application_request

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
