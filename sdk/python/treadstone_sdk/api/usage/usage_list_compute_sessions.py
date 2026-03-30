from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.compute_session_list_response import ComputeSessionListResponse
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    status: str | Unset = "all",
    limit: int | Unset = 20,
    offset: int | Unset = 0,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["status"] = status

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/usage/sessions",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ComputeSessionListResponse | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = ComputeSessionListResponse.from_dict(response.json())

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
) -> Response[ComputeSessionListResponse | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    status: str | Unset = "all",
    limit: int | Unset = 20,
    offset: int | Unset = 0,
) -> Response[ComputeSessionListResponse | HTTPValidationError]:
    """List Compute Sessions

    Args:
        status (str | Unset):  Default: 'all'.
        limit (int | Unset):  Default: 20.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ComputeSessionListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        status=status,
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
    status: str | Unset = "all",
    limit: int | Unset = 20,
    offset: int | Unset = 0,
) -> ComputeSessionListResponse | HTTPValidationError | None:
    """List Compute Sessions

    Args:
        status (str | Unset):  Default: 'all'.
        limit (int | Unset):  Default: 20.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ComputeSessionListResponse | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        status=status,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    status: str | Unset = "all",
    limit: int | Unset = 20,
    offset: int | Unset = 0,
) -> Response[ComputeSessionListResponse | HTTPValidationError]:
    """List Compute Sessions

    Args:
        status (str | Unset):  Default: 'all'.
        limit (int | Unset):  Default: 20.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ComputeSessionListResponse | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        status=status,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    status: str | Unset = "all",
    limit: int | Unset = 20,
    offset: int | Unset = 0,
) -> ComputeSessionListResponse | HTTPValidationError | None:
    """List Compute Sessions

    Args:
        status (str | Unset):  Default: 'all'.
        limit (int | Unset):  Default: 20.
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ComputeSessionListResponse | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            status=status,
            limit=limit,
            offset=offset,
        )
    ).parsed
