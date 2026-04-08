from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.sandbox_detail_response import SandboxDetailResponse
from ...models.update_sandbox_request import UpdateSandboxRequest
from ...types import Response


def _get_kwargs(
    sandbox_id: str,
    *,
    body: UpdateSandboxRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/sandboxes/{sandbox_id}".format(
            sandbox_id=quote(str(sandbox_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | SandboxDetailResponse | None:
    if response.status_code == 200:
        response_200 = SandboxDetailResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | SandboxDetailResponse]:
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
    body: UpdateSandboxRequest,
) -> Response[HTTPValidationError | SandboxDetailResponse]:
    """Update Sandbox

    Args:
        sandbox_id (str):
        body (UpdateSandboxRequest): Partial update for sandbox metadata (control plane).
            Immutable fields: template, persist, storage.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxDetailResponse]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateSandboxRequest,
) -> HTTPValidationError | SandboxDetailResponse | None:
    """Update Sandbox

    Args:
        sandbox_id (str):
        body (UpdateSandboxRequest): Partial update for sandbox metadata (control plane).
            Immutable fields: template, persist, storage.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxDetailResponse
    """

    return sync_detailed(
        sandbox_id=sandbox_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateSandboxRequest,
) -> Response[HTTPValidationError | SandboxDetailResponse]:
    """Update Sandbox

    Args:
        sandbox_id (str):
        body (UpdateSandboxRequest): Partial update for sandbox metadata (control plane).
            Immutable fields: template, persist, storage.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | SandboxDetailResponse]
    """

    kwargs = _get_kwargs(
        sandbox_id=sandbox_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    sandbox_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateSandboxRequest,
) -> HTTPValidationError | SandboxDetailResponse | None:
    """Update Sandbox

    Args:
        sandbox_id (str):
        body (UpdateSandboxRequest): Partial update for sandbox metadata (control plane).
            Immutable fields: template, persist, storage.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | SandboxDetailResponse
    """

    return (
        await asyncio_detailed(
            sandbox_id=sandbox_id,
            client=client,
            body=body,
        )
    ).parsed
