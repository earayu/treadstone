from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.waitlist_application_request import WaitlistApplicationRequest
from ...models.waitlist_application_response import WaitlistApplicationResponse
from ...types import Response


def _get_kwargs(
    *,
    body: WaitlistApplicationRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/waitlist",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    if response.status_code == 201:
        response_201 = WaitlistApplicationResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: WaitlistApplicationRequest,
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    """Submit Waitlist Application

     Submit a waitlist application for Pro or Ultra plan access.

    No authentication required — users may apply before registering. Multiple
    applications from the same email (including same tier) are allowed.

    Args:
        body (WaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WaitlistApplicationResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: WaitlistApplicationRequest,
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    """Submit Waitlist Application

     Submit a waitlist application for Pro or Ultra plan access.

    No authentication required — users may apply before registering. Multiple
    applications from the same email (including same tier) are allowed.

    Args:
        body (WaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WaitlistApplicationResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: WaitlistApplicationRequest,
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    """Submit Waitlist Application

     Submit a waitlist application for Pro or Ultra plan access.

    No authentication required — users may apply before registering. Multiple
    applications from the same email (including same tier) are allowed.

    Args:
        body (WaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WaitlistApplicationResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: WaitlistApplicationRequest,
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    """Submit Waitlist Application

     Submit a waitlist application for Pro or Ultra plan access.

    No authentication required — users may apply before registering. Multiple
    applications from the same email (including same tier) are allowed.

    Args:
        body (WaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WaitlistApplicationResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
