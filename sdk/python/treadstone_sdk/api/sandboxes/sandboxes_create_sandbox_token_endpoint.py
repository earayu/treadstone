from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_sandbox_token_request import CreateSandboxTokenRequest
from ...models.http_validation_error import HTTPValidationError
from ...models.sandbox_token_response import SandboxTokenResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    sandbox_id: str,
    *,
    body: CreateSandboxTokenRequest,
    user_db: Any | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    params["user_db"] = user_db

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/sandboxes/{sandbox_id}/token".format(
            sandbox_id=quote(str(sandbox_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SandboxTokenResponse | None:
    if response.status_code == 201:
        response_201 = SandboxTokenResponse.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | SandboxTokenResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: CreateSandboxTokenRequest,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | SandboxTokenResponse]:
    """Create Sandbox Token Endpoint

    Args:
        sandbox_id (str):
        user_db (Any | Unset):
        body (CreateSandboxTokenRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxTokenResponse]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        body=body,
        user_db=user_db,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: CreateSandboxTokenRequest,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | SandboxTokenResponse | None:
    """Create Sandbox Token Endpoint

    Args:
        sandbox_id (str):
        user_db (Any | Unset):
        body (CreateSandboxTokenRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxTokenResponse
    """

    return sync_detailed(
        sandbox_id=sandbox_id,
        client=client,
        body=body,
        user_db=user_db,
    ).parsed


async def asyncio_detailed(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: CreateSandboxTokenRequest,
    user_db: Any | Unset = UNSET,
) -> Response[HTTPValidationError | SandboxTokenResponse]:
    """Create Sandbox Token Endpoint

    Args:
        sandbox_id (str):
        user_db (Any | Unset):
        body (CreateSandboxTokenRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxTokenResponse]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        body=body,
        user_db=user_db,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: CreateSandboxTokenRequest,
    user_db: Any | Unset = UNSET,
) -> HTTPValidationError | SandboxTokenResponse | None:
    """Create Sandbox Token Endpoint

    Args:
        sandbox_id (str):
        user_db (Any | Unset):
        body (CreateSandboxTokenRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxTokenResponse
    """

    return (
        await asyncio_detailed(
            sandbox_id=sandbox_id,
            client=client,
            body=body,
            user_db=user_db,
        )
    ).parsed
