from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...types import UNSET, Response, Unset


def _get_kwargs(
    flow_id: str,
    *,
    x_flow_secret: None | str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_flow_secret, Unset):
        headers["x-flow-secret"] = x_flow_secret

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/auth/cli/flows/{flow_id}/status".format(
            flow_id=quote(str(flow_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = response.json()
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
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    flow_id: str,
    *,
    client: AuthenticatedClient | Client,
    x_flow_secret: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Poll Cli Flow

     Poll the status of a CLI login flow.

    Args:
        flow_id (str):
        x_flow_secret (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        flow_id=flow_id,
        x_flow_secret=x_flow_secret,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    flow_id: str,
    *,
    client: AuthenticatedClient | Client,
    x_flow_secret: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Poll Cli Flow

     Poll the status of a CLI login flow.

    Args:
        flow_id (str):
        x_flow_secret (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        flow_id=flow_id,
        client=client,
        x_flow_secret=x_flow_secret,
    ).parsed


async def asyncio_detailed(
    flow_id: str,
    *,
    client: AuthenticatedClient | Client,
    x_flow_secret: None | str | Unset = UNSET,
) -> Response[Any | HTTPValidationError]:
    """Poll Cli Flow

     Poll the status of a CLI login flow.

    Args:
        flow_id (str):
        x_flow_secret (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        flow_id=flow_id,
        x_flow_secret=x_flow_secret,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    flow_id: str,
    *,
    client: AuthenticatedClient | Client,
    x_flow_secret: None | str | Unset = UNSET,
) -> Any | HTTPValidationError | None:
    """Poll Cli Flow

     Poll the status of a CLI login flow.

    Args:
        flow_id (str):
        x_flow_secret (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            flow_id=flow_id,
            client=client,
            x_flow_secret=x_flow_secret,
        )
    ).parsed
