from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.sandbox_list_response import SandboxListResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    label: list[str] | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
    user_db: Any | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    json_label: list[str] | Unset = UNSET
    if not isinstance(label, Unset):
        json_label = label

    params["label"] = json_label

    params["limit"] = limit

    params["offset"] = offset

    params["user_db"] = user_db

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/sandboxes",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SandboxListResponse | None:
    if response.status_code == 200:
        response_200 = SandboxListResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | SandboxListResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    label: list[str] | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | SandboxListResponse]:
    """List Sandboxes

    Args:
        label (list[str] | Unset):
        limit (int | Unset): Maximum number of items to return. Default: 100.
        offset (int | Unset): Number of items to skip. Default: 0.
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxListResponse]
    """

    kwargs = _get_kwargs(
        label=label,
        limit=limit,
        offset=offset,
        user_db=user_db,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    label: list[str] | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | SandboxListResponse | None:
    """List Sandboxes

    Args:
        label (list[str] | Unset):
        limit (int | Unset): Maximum number of items to return. Default: 100.
        offset (int | Unset): Number of items to skip. Default: 0.
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxListResponse
    """

    return sync_detailed(
        client=client,
        label=label,
        limit=limit,
        offset=offset,
        user_db=user_db,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    label: list[str] | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | SandboxListResponse]:
    """List Sandboxes

    Args:
        label (list[str] | Unset):
        limit (int | Unset): Maximum number of items to return. Default: 100.
        offset (int | Unset): Number of items to skip. Default: 0.
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxListResponse]
    """

    kwargs = _get_kwargs(
        label=label,
        limit=limit,
        offset=offset,
        user_db=user_db,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    label: list[str] | Unset = UNSET,
    limit: int | Unset = 100,
    offset: int | Unset = 0,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | SandboxListResponse | None:
    """List Sandboxes

    Args:
        label (list[str] | Unset):
        limit (int | Unset): Maximum number of items to return. Default: 100.
        offset (int | Unset): Number of items to skip. Default: 0.
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxListResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            label=label,
            limit=limit,
            offset=offset,
            user_db=user_db,
        )
    ).parsed
