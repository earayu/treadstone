from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_key_summary import ApiKeySummary
from ...models.http_validation_error import HTTPValidationError
from ...models.update_api_key_request import UpdateApiKeyRequest
from ...types import UNSET, Response, Unset


def _get_kwargs(
    key_id: str,
    *,
    body: UpdateApiKeyRequest,
    user_db: Any | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    params["user_db"] = user_db

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/v1/auth/api-keys/{key_id}".format(
            key_id=quote(str(key_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiKeySummary | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = ApiKeySummary.from_dict(response.json())

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
) -> Response[ApiKeySummary | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    key_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateApiKeyRequest,
    user_db: Any | Unset = UNSET,
) -> Response[ApiKeySummary | HTTPValidationError]:
    """Update Api Key

    Args:
        key_id (str):
        user_db (Any | Unset):
        body (UpdateApiKeyRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiKeySummary | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        key_id=key_id,
        body=body,
        user_db=user_db,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    key_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateApiKeyRequest,
    user_db: Any | Unset = UNSET,
) -> ApiKeySummary | HTTPValidationError | None:
    """Update Api Key

    Args:
        key_id (str):
        user_db (Any | Unset):
        body (UpdateApiKeyRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiKeySummary | HTTPValidationError
    """

    return sync_detailed(
        key_id=key_id,
        client=client,
        body=body,
        user_db=user_db,
    ).parsed


async def asyncio_detailed(
    key_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateApiKeyRequest,
    user_db: Any | Unset = UNSET,
) -> Response[ApiKeySummary | HTTPValidationError]:
    """Update Api Key

    Args:
        key_id (str):
        user_db (Any | Unset):
        body (UpdateApiKeyRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiKeySummary | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        key_id=key_id,
        body=body,
        user_db=user_db,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    key_id: str,
    *,
    client: AuthenticatedClient,
    body: UpdateApiKeyRequest,
    user_db: Any | Unset = UNSET,
) -> ApiKeySummary | HTTPValidationError | None:
    """Update Api Key

    Args:
        key_id (str):
        user_db (Any | Unset):
        body (UpdateApiKeyRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiKeySummary | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            key_id=key_id,
            client=client,
            body=body,
            user_db=user_db,
        )
    ).parsed
