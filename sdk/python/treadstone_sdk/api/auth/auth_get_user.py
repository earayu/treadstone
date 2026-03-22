from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.user_detail_response import UserDetailResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    user_db: Any | Unset = UNSET,
) -> dict[str, Any]:
    params: dict[str, Any] = {}

    params["user_db"] = user_db

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/auth/user",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | UserDetailResponse | None:
    if response.status_code == 200:
        response_200 = UserDetailResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | UserDetailResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | UserDetailResponse]:
    """Get User

    Args:
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UserDetailResponse]
    """

    kwargs = _get_kwargs(
        user_db=user_db,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | UserDetailResponse | None:
    """Get User

    Args:
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UserDetailResponse
    """

    return sync_detailed(
        client=client,
        user_db=user_db,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | UserDetailResponse]:
    """Get User

    Args:
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UserDetailResponse]
    """

    kwargs = _get_kwargs(
        user_db=user_db,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | UserDetailResponse | None:
    """Get User

    Args:
        user_db (Any | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UserDetailResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            user_db=user_db,
        )
    ).parsed
