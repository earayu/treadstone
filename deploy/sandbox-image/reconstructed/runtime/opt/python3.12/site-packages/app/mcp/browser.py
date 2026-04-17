from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any, Dict, get_args

from mcp.server.fastmcp import Context, Image
from mcp.server.session import ServerSession

from app.core.service_container import services
from app.models.browser import AnyAction, BrowserInfoResult


if TYPE_CHECKING:
    from app.services.browser import BrowserService

from .app import mcp


logger = logging.getLogger(__name__)


# Build ACTION_MODELS dynamically from AnyAction Union type
def _build_action_models():
    """Build the action models mapping from the AnyAction Union type."""
    models = {}
    for action_class in get_args(AnyAction):
        # Get the default action_type value from the class
        # Each action class has a Literal['ACTION_TYPE'] field with a default value
        action_type = action_class.model_fields['action_type'].default
        models[action_type] = action_class
    return models


# Create the mapping once at module load time
ACTION_MODELS = _build_action_models()


# Generate documentation from the actual models
def _generate_action_docs():
    """Generate documentation string from action models."""
    docs = []
    for action_type, model_class in sorted(ACTION_MODELS.items()):
        params = []
        for field_name, field_info in model_class.model_fields.items():
            if field_name == 'action_type':
                continue
            field_type = field_info.annotation
            required = field_info.is_required()
            param_str = f'{field_name}: {field_type.__name__ if hasattr(field_type, "__name__") else str(field_type)}'
            if not required:
                param_str += '?'
            params.append(param_str)

        param_list = ', '.join(params) if params else ''
        docs.append(
            f"    - {action_type}: {{action_type: '{action_type}'{', ' + param_list if param_list else ''}}}"
        )

    return '\n'.join(docs)


@mcp.tool(structured_output=False)
async def get_browser_info(ctx: Context[ServerSession, None]) -> BrowserInfoResult:
    """Get information about browser, like cdp url, viewport size, etc.

    Args:
        request (Dict): The incoming request context.
    """

    request = ctx.request_context.request
    browser_service: 'BrowserService' = services.get('browser_service')
    result = await browser_service.get_browser_info(request=request)

    return result.model_dump()


@mcp.tool(structured_output=False)
async def browser_screenshot() -> Image:
    """Take a screenshot of the current display.

    Returns:
        Image: A screenshot of the current display in JPEG format with metadata.
    """
    browser_service: 'BrowserService' = services.get('browser_service')

    screenshot, result = await browser_service.task_screenshot()

    buffer = io.BytesIO()
    screenshot.convert('RGB').save(buffer, format='JPEG', quality=60, optimize=True)

    return Image(
        data=buffer.getvalue(),
        format='jpeg',
    )


@mcp.tool(
    structured_output=False,
    description="""Execute a browser action on the current display.

Args:
    `action`: Dictionary containing `action_type` and relevant parameters.
            The `action_type` determines which parameters are required.

Action types and their parameters (auto-generated from models):
{action_docs}

Returns:
    Dict containing `status` and `action_performed`

Raises:
    ValueError: If `action_type` is invalid or required parameters are missing
    """.format(action_docs=_generate_action_docs()),
)
async def browser_execute_action(
    action: Dict[str, Any],
) -> Dict[str, Any]:
    browser_service: 'BrowserService' = services.get('browser_service')

    action_type = action.pop('action_type')
    if not action_type:
        raise ValueError('action_type is required')

    # Get the appropriate model class from the dynamically built mapping
    model_class = ACTION_MODELS.get(action_type)
    if not model_class:
        available_types = ', '.join(sorted(ACTION_MODELS.keys()))
        raise ValueError(
            f'Invalid action_type: {action_type}. Available types: {available_types}'
        )

    # Create the action instance from the dictionary
    # The Pydantic model will validate required fields
    try:
        action_instance = model_class(**action)
    except Exception as e:
        raise ValueError(f'Failed to create {action_type} action: {str(e)}')

    # Execute the action
    action_response = await browser_service.execute_action(action_instance)
    return action_response.model_dump()
