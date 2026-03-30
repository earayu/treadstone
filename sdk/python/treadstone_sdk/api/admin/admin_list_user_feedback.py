from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.feedback_list_response import FeedbackListResponse
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = 50,
    offset: int | Unset = 0,
    email: None | str | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["limit"] = limit

    params["offset"] = offset

    json_email: None | str | Unset
    if isinstance(email, Unset):
        json_email = UNSET
    else:
        json_email = email
    params["email"] = json_email

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/admin/support/feedback",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> FeedbackListResponse | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = FeedbackListResponse.from_dict(response.json())

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
) -> Response[FeedbackListResponse | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
    offset: int | Unset = 0,
    email: None | str | Unset = UNSET,
) -> Response[FeedbackListResponse | HTTPValidationError]:
    """List User Feedback

     List user-submitted support feedback (newest first).

    Args:
        limit (int | Unset):  Default: 50.
        offset (int | Unset):  Default: 0.
        email (None | str | Unset): Optional case-insensitive substring match on submitter email.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FeedbackListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        limit=limit,
        offset=offset,
        email=email,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
    offset: int | Unset = 0,
    email: None | str | Unset = UNSET,
) -> FeedbackListResponse | HTTPValidationError | None:
    """List User Feedback

     List user-submitted support feedback (newest first).

    Args:
        limit (int | Unset):  Default: 50.
        offset (int | Unset):  Default: 0.
        email (None | str | Unset): Optional case-insensitive substring match on submitter email.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FeedbackListResponse | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        limit=limit,
        offset=offset,
        email=email,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
    offset: int | Unset = 0,
    email: None | str | Unset = UNSET,
) -> Response[FeedbackListResponse | HTTPValidationError]:
    """List User Feedback

     List user-submitted support feedback (newest first).

    Args:
        limit (int | Unset):  Default: 50.
        offset (int | Unset):  Default: 0.
        email (None | str | Unset): Optional case-insensitive substring match on submitter email.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[FeedbackListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        limit=limit,
        offset=offset,
        email=email,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    limit: int | Unset = 50,
    offset: int | Unset = 0,
    email: None | str | Unset = UNSET,
) -> FeedbackListResponse | HTTPValidationError | None:
    """List User Feedback

     List user-submitted support feedback (newest first).

    Args:
        limit (int | Unset):  Default: 50.
        offset (int | Unset):  Default: 0.
        email (None | str | Unset): Optional case-insensitive substring match on submitter email.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        FeedbackListResponse | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
            offset=offset,
            email=email,
        )
    ).parsed
