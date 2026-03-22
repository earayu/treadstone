from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.change_password_request import ChangePasswordRequest
from ...models.http_validation_error import HTTPValidationError
from ...models.message_response import MessageResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: ChangePasswordRequest,
    user_db: Any | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    params["user_db"] = user_db

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/auth/change-password",
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | MessageResponse | None:
    if response.status_code == 200:
        response_200 = MessageResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | MessageResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: ChangePasswordRequest,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | MessageResponse]:
    """Change Password

    Args:
        user_db (Any | Unset):
        body (ChangePasswordRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MessageResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        user_db=user_db,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    body: ChangePasswordRequest,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | MessageResponse | None:
    """Change Password

    Args:
        user_db (Any | Unset):
        body (ChangePasswordRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MessageResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        user_db=user_db,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: ChangePasswordRequest,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | MessageResponse]:
    """Change Password

    Args:
        user_db (Any | Unset):
        body (ChangePasswordRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | MessageResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        user_db=user_db,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    body: ChangePasswordRequest,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | MessageResponse | None:
    """Change Password

    Args:
        user_db (Any | Unset):
        body (ChangePasswordRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | MessageResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            user_db=user_db,
        )
    ).parsed
