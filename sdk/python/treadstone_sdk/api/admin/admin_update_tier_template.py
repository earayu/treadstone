from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.update_tier_template_request import UpdateTierTemplateRequest
from ...models.update_tier_template_response import UpdateTierTemplateResponse
from ...types import Response


def _get_kwargs(
    tier_name: str,
    *,
    body: UpdateTierTemplateRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/admin/tier-templates/{tier_name}".format(
            tier_name=quote(str(tier_name), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | UpdateTierTemplateResponse | None:
    if response.status_code == 200:
        response_200 = UpdateTierTemplateResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | UpdateTierTemplateResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    tier_name: str,
    *,
    client: AuthenticatedClient,
    body: UpdateTierTemplateRequest,
) -> Response[HTTPValidationError | UpdateTierTemplateResponse]:
    """Update Tier Template

    Args:
        tier_name (str):
        body (UpdateTierTemplateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateTierTemplateResponse]
    """

    kwargs = _get_kwargs(
        tier_name=tier_name,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    tier_name: str,
    *,
    client: AuthenticatedClient,
    body: UpdateTierTemplateRequest,
) -> HTTPValidationError | UpdateTierTemplateResponse | None:
    """Update Tier Template

    Args:
        tier_name (str):
        body (UpdateTierTemplateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateTierTemplateResponse
    """

    return sync_detailed(
        tier_name=tier_name,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    tier_name: str,
    *,
    client: AuthenticatedClient,
    body: UpdateTierTemplateRequest,
) -> Response[HTTPValidationError | UpdateTierTemplateResponse]:
    """Update Tier Template

    Args:
        tier_name (str):
        body (UpdateTierTemplateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | UpdateTierTemplateResponse]
    """

    kwargs = _get_kwargs(
        tier_name=tier_name,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    tier_name: str,
    *,
    client: AuthenticatedClient,
    body: UpdateTierTemplateRequest,
) -> HTTPValidationError | UpdateTierTemplateResponse | None:
    """Update Tier Template

    Args:
        tier_name (str):
        body (UpdateTierTemplateRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | UpdateTierTemplateResponse
    """

    return (
        await asyncio_detailed(
            tier_name=tier_name,
            client=client,
            body=body,
        )
    ).parsed
