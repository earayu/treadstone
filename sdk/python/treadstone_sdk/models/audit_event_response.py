from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field
from dateutil.parser import isoparse

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.audit_event_response_metadata import AuditEventResponseMetadata


T = TypeVar("T", bound="AuditEventResponse")


@_attrs_define
class AuditEventResponse:
    """
    Attributes:
        id (str):
        created_at (datetime.datetime):
        actor_type (str):
        action (str):
        target_type (str):
        result (str):
        actor_user_id (None | str | Unset):
        actor_api_key_id (None | str | Unset):
        credential_type (None | str | Unset):
        target_id (None | str | Unset):
        error_code (None | str | Unset):
        request_id (None | str | Unset):
        ip (None | str | Unset):
        user_agent (None | str | Unset):
        metadata (AuditEventResponseMetadata | Unset):
    """

    id: str
    created_at: datetime.datetime
    actor_type: str
    action: str
    target_type: str
    result: str
    actor_user_id: None | str | Unset = UNSET
    actor_api_key_id: None | str | Unset = UNSET
    credential_type: None | str | Unset = UNSET
    target_id: None | str | Unset = UNSET
    error_code: None | str | Unset = UNSET
    request_id: None | str | Unset = UNSET
    ip: None | str | Unset = UNSET
    user_agent: None | str | Unset = UNSET
    metadata: AuditEventResponseMetadata | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        created_at = self.created_at.isoformat()

        actor_type = self.actor_type

        action = self.action

        target_type = self.target_type

        result = self.result

        actor_user_id: None | str | Unset
        if isinstance(self.actor_user_id, Unset):
            actor_user_id = UNSET
        else:
            actor_user_id = self.actor_user_id

        actor_api_key_id: None | str | Unset
        if isinstance(self.actor_api_key_id, Unset):
            actor_api_key_id = UNSET
        else:
            actor_api_key_id = self.actor_api_key_id

        credential_type: None | str | Unset
        if isinstance(self.credential_type, Unset):
            credential_type = UNSET
        else:
            credential_type = self.credential_type

        target_id: None | str | Unset
        if isinstance(self.target_id, Unset):
            target_id = UNSET
        else:
            target_id = self.target_id

        error_code: None | str | Unset
        if isinstance(self.error_code, Unset):
            error_code = UNSET
        else:
            error_code = self.error_code

        request_id: None | str | Unset
        if isinstance(self.request_id, Unset):
            request_id = UNSET
        else:
            request_id = self.request_id

        ip: None | str | Unset
        if isinstance(self.ip, Unset):
            ip = UNSET
        else:
            ip = self.ip

        user_agent: None | str | Unset
        if isinstance(self.user_agent, Unset):
            user_agent = UNSET
        else:
            user_agent = self.user_agent

        metadata: dict[str, Any] | Unset = UNSET
        if not isinstance(self.metadata, Unset):
            metadata = self.metadata.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "created_at": created_at,
                "actor_type": actor_type,
                "action": action,
                "target_type": target_type,
                "result": result,
            }
        )
        if actor_user_id is not UNSET:
            field_dict["actor_user_id"] = actor_user_id
        if actor_api_key_id is not UNSET:
            field_dict["actor_api_key_id"] = actor_api_key_id
        if credential_type is not UNSET:
            field_dict["credential_type"] = credential_type
        if target_id is not UNSET:
            field_dict["target_id"] = target_id
        if error_code is not UNSET:
            field_dict["error_code"] = error_code
        if request_id is not UNSET:
            field_dict["request_id"] = request_id
        if ip is not UNSET:
            field_dict["ip"] = ip
        if user_agent is not UNSET:
            field_dict["user_agent"] = user_agent
        if metadata is not UNSET:
            field_dict["metadata"] = metadata

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.audit_event_response_metadata import AuditEventResponseMetadata

        d = dict(src_dict)
        id = d.pop("id")

        created_at = isoparse(d.pop("created_at"))

        actor_type = d.pop("actor_type")

        action = d.pop("action")

        target_type = d.pop("target_type")

        result = d.pop("result")

        def _parse_actor_user_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        actor_user_id = _parse_actor_user_id(d.pop("actor_user_id", UNSET))

        def _parse_actor_api_key_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        actor_api_key_id = _parse_actor_api_key_id(d.pop("actor_api_key_id", UNSET))

        def _parse_credential_type(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        credential_type = _parse_credential_type(d.pop("credential_type", UNSET))

        def _parse_target_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        target_id = _parse_target_id(d.pop("target_id", UNSET))

        def _parse_error_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        error_code = _parse_error_code(d.pop("error_code", UNSET))

        def _parse_request_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        request_id = _parse_request_id(d.pop("request_id", UNSET))

        def _parse_ip(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        ip = _parse_ip(d.pop("ip", UNSET))

        def _parse_user_agent(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        user_agent = _parse_user_agent(d.pop("user_agent", UNSET))

        _metadata = d.pop("metadata", UNSET)
        metadata: AuditEventResponseMetadata | Unset
        if isinstance(_metadata, Unset):
            metadata = UNSET
        else:
            metadata = AuditEventResponseMetadata.from_dict(_metadata)

        audit_event_response = cls(
            id=id,
            created_at=created_at,
            actor_type=actor_type,
            action=action,
            target_type=target_type,
            result=result,
            actor_user_id=actor_user_id,
            actor_api_key_id=actor_api_key_id,
            credential_type=credential_type,
            target_id=target_id,
            error_code=error_code,
            request_id=request_id,
            ip=ip,
            user_agent=user_agent,
            metadata=metadata,
        )

        audit_event_response.additional_properties = d
        return audit_event_response

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
