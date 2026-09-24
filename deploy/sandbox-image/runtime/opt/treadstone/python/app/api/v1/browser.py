import io
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from starlette.responses import StreamingResponse

from app.core.service_container import services
from app.models.browser import ActionResponse, AnyAction, BrowserInfoResult
from app.schemas.response import Response
from app.schemas.browser import BrowserConfigRequest
from app.services.browser import BrowserService


logger = logging.getLogger(__name__)


router = APIRouter()


@router.get(
    '/info',
    response_model=Response[BrowserInfoResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'browser',
        'x-fern-sdk-method-name': 'get_info',
    },
)
async def get_browser_info(request: Request):
    """
    Get information about browser, like cdp url, viewport size, etc.
    """
    try:
        browser_service: BrowserService = services.get('browser_service')
        result = await browser_service.get_browser_info(request=request)

        return Response(
            success=True,
            message='Browser info retrieved',
            data=result,
        )

    except Exception as e:
        logger.error(f'Error getting Browser info: {e}')
        raise HTTPException(status_code=500, detail=f'Failed to get info: {str(e)}')


@router.get(
    '/screenshot',
    openapi_extra={
        'x-fern-sdk-group-name': 'browser',
        'x-fern-sdk-method-name': 'screenshot',
    },
    response_class=StreamingResponse,
    responses={
        200: {
            'description': 'Screenshot image',
            'content': {'image/png': {}},
            'headers': {
                'x-screen-width': {
                    'description': 'Screen width',
                    'schema': {'type': 'string'},
                },
                'x-screen-height': {
                    'description': 'Screen height',
                    'schema': {'type': 'string'},
                },
                'x-image-width': {
                    'description': 'Image width',
                    'schema': {'type': 'string'},
                },
                'x-image-height': {
                    'description': 'Image height',
                    'schema': {'type': 'string'},
                },
            },
        }
    },
)
async def take_screenshot():
    """Take a screenshot of the current display.

    Returns:
        StreamingResponse: PNG image data with proper headers including display and screenshot dimensions
    """

    browser_service: BrowserService = services.get('browser_service')

    img, result = await browser_service.task_screenshot()

    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type='image/png',
        headers={
            'x-screen-width': str(result.screenshot_width),
            'x-screen-height': str(result.display_height),
            'x-image-width': str(result.screenshot_width),
            'x-image-height': str(result.screenshot_height),
        },
    )


@router.post(
    '/actions',
    openapi_extra={
        'x-fern-sdk-group-name': 'browser',
        'x-fern-sdk-method-name': 'execute_action',
    },
    response_model=ActionResponse,
)
async def execute_action(
    action: Annotated[AnyAction, Field(discriminator='action_type')],
) -> ActionResponse:
    """Execute a validated action on the current display."""
    try:
        browser_service: BrowserService = services.get('browser_service')
        action_response = await browser_service.execute_action(action)

        return action_response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error during action execution: {e}'
        )

@router.post(
    '/config',
    openapi_extra={
        'x-fern-sdk-group-name': 'browser',
        'x-fern-sdk-method-name': 'set_config',
    },
    response_model=Response,
)
async def set_config(
    request: BrowserConfigRequest
) -> ActionResponse:
    """Execute a validated action on the current display."""
    try:
        browser_service: BrowserService = services.get('browser_service')


        if request.resolution:
            message = browser_service.set_resolution(
                width=request.resolution.width,
                height=request.resolution.height
            )
            return Response(
                success=True,
                message=message,
                data=None
            )

        return Response(
            success=False,
            message="No configuration changes provided",
            data=None
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'Error during action execution: {e}'
        )
