from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.update_waitlist_application_request import UpdateWaitlistApplicationRequest
from ...models.waitlist_application_response import WaitlistApplicationResponse
from ...types import Response


def _get_kwargs(
    application_id: str,
    *,
    body: UpdateWaitlistApplicationRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/admin/waitlist/{application_id}".format(
            application_id=quote(str(application_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    if response.status_code == 200:
        response_200 = WaitlistApplicationResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    application_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateWaitlistApplicationRequest,
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    """Update Waitlist Application

     Approve or reject a waitlist application.

    Args:
        application_id (str):
        body (UpdateWaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WaitlistApplicationResponse]
    """

    kwargs = _get_kwargs(
        application_id=application_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    application_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateWaitlistApplicationRequest,
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    """Update Waitlist Application

     Approve or reject a waitlist application.

    Args:
        application_id (str):
        body (UpdateWaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WaitlistApplicationResponse
    """

    return sync_detailed(
        application_id=application_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    application_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateWaitlistApplicationRequest,
) -> Response[HTTPValidationError | WaitlistApplicationResponse]:
    """Update Waitlist Application

     Approve or reject a waitlist application.

    Args:
        application_id (str):
        body (UpdateWaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | WaitlistApplicationResponse]
    """

    kwargs = _get_kwargs(
        application_id=application_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    application_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateWaitlistApplicationRequest,
) -> HTTPValidationError | WaitlistApplicationResponse | None:
    """Update Waitlist Application

     Approve or reject a waitlist application.

    Args:
        application_id (str):
        body (UpdateWaitlistApplicationRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | WaitlistApplicationResponse
    """

    return (
        await asyncio_detailed(
            application_id=application_id,
            client=client,
            body=body,
        )
    ).parsed
