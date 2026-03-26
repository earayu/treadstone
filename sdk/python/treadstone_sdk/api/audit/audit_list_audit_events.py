import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.audit_event_list_response import AuditEventListResponse
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    action: None | str | Unset = UNSET,
    target_type: None | str | Unset = UNSET,
    target_id: None | str | Unset = UNSET,
    actor_user_id: None | str | Unset = UNSET,
    request_id: None | str | Unset = UNSET,
    result: None | str | Unset = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_action: None | str | Unset
    if isinstance(action, Unset):
        json_action = UNSET
    else:
        json_action = action
    params["action"] = json_action

    json_target_type: None | str | Unset
    if isinstance(target_type, Unset):
        json_target_type = UNSET
    else:
        json_target_type = target_type
    params["target_type"] = json_target_type

    json_target_id: None | str | Unset
    if isinstance(target_id, Unset):
        json_target_id = UNSET
    else:
        json_target_id = target_id
    params["target_id"] = json_target_id

    json_actor_user_id: None | str | Unset
    if isinstance(actor_user_id, Unset):
        json_actor_user_id = UNSET
    else:
        json_actor_user_id = actor_user_id
    params["actor_user_id"] = json_actor_user_id

    json_request_id: None | str | Unset
    if isinstance(request_id, Unset):
        json_request_id = UNSET
    else:
        json_request_id = request_id
    params["request_id"] = json_request_id

    json_result: None | str | Unset
    if isinstance(result, Unset):
        json_result = UNSET
    else:
        json_result = result
    params["result"] = json_result

    json_since: None | str | Unset
    if isinstance(since, Unset):
        json_since = UNSET
    elif isinstance(since, datetime.datetime):
        json_since = since.isoformat()
    else:
        json_since = since
    params["since"] = json_since

    json_until: None | str | Unset
    if isinstance(until, Unset):
        json_until = UNSET
    elif isinstance(until, datetime.datetime):
        json_until = until.isoformat()
    else:
        json_until = until
    params["until"] = json_until

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/audit/events",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AuditEventListResponse | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = AuditEventListResponse.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AuditEventListResponse | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    target_type: None | str | Unset = UNSET,
    target_id: None | str | Unset = UNSET,
    actor_user_id: None | str | Unset = UNSET,
    request_id: None | str | Unset = UNSET,
    result: None | str | Unset = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
) -> Response[AuditEventListResponse | HTTPValidationError]:
    """List Audit Events

    Args:
        action (None | str | Unset):
        target_type (None | str | Unset):
        target_id (None | str | Unset):
        actor_user_id (None | str | Unset):
        request_id (None | str | Unset):
        result (None | str | Unset):
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 100.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuditEventListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result=result,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    target_type: None | str | Unset = UNSET,
    target_id: None | str | Unset = UNSET,
    actor_user_id: None | str | Unset = UNSET,
    request_id: None | str | Unset = UNSET,
    result: None | str | Unset = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
) -> AuditEventListResponse | HTTPValidationError | None:
    """List Audit Events

    Args:
        action (None | str | Unset):
        target_type (None | str | Unset):
        target_id (None | str | Unset):
        actor_user_id (None | str | Unset):
        request_id (None | str | Unset):
        result (None | str | Unset):
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 100.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuditEventListResponse | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result=result,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    target_type: None | str | Unset = UNSET,
    target_id: None | str | Unset = UNSET,
    actor_user_id: None | str | Unset = UNSET,
    request_id: None | str | Unset = UNSET,
    result: None | str | Unset = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
) -> Response[AuditEventListResponse | HTTPValidationError]:
    """List Audit Events

    Args:
        action (None | str | Unset):
        target_type (None | str | Unset):
        target_id (None | str | Unset):
        actor_user_id (None | str | Unset):
        request_id (None | str | Unset):
        result (None | str | Unset):
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 100.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuditEventListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        action=action,
        target_type=target_type,
        target_id=target_id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        result=result,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    action: None | str | Unset = UNSET,
    target_type: None | str | Unset = UNSET,
    target_id: None | str | Unset = UNSET,
    actor_user_id: None | str | Unset = UNSET,
    request_id: None | str | Unset = UNSET,
    result: None | str | Unset = UNSET,
    since: datetime.datetime | None | Unset = UNSET,
    until: datetime.datetime | None | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
) -> AuditEventListResponse | HTTPValidationError | None:
    """List Audit Events

    Args:
        action (None | str | Unset):
        target_type (None | str | Unset):
        target_id (None | str | Unset):
        actor_user_id (None | str | Unset):
        request_id (None | str | Unset):
        result (None | str | Unset):
        since (datetime.datetime | None | Unset):
        until (datetime.datetime | None | Unset):
        limit (int | Unset):  Default: 100.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuditEventListResponse | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            result=result,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )
    ).parsed
