"""
Sandbox environment MCP tools
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Literal

from app.api.v1.sandbox import get_node_packages, get_python_packages
from app.core.service_container import services

from .app import mcp


if TYPE_CHECKING:
    from app.services.sandbox import SandboxService

logger = logging.getLogger(__name__)


@mcp.tool(structured_output=False)
async def get_context() -> Dict[str, Any]:
    """Get sandbox environment information. aio system's version.

    Returns:
        Dict containing aio sandbox's environment info, version, and home directory
    """
    try:
        sandbox_service: 'SandboxService' = services.get('sandbox_service')
        sandbox_info = sandbox_service.get_sandbox_info()

        return json.dumps(
            {
                'info': sandbox_info.info,
                'home_dir': sandbox_info.home_dir,
            }
        )
    except Exception as e:
        return {'success': False, 'error': str(e)}


@mcp.tool(structured_output=False)
async def get_packages(language: Literal['python', 'nodejs'] = None) -> str:
    """Get installed packages by language.

    Args:
        language: Optional language filter ('python' or 'nodejs')

    Returns: String listing installed packages
    """

    if language is None or language in ['python', 'py']:
        python_packages = get_python_packages()
        return python_packages
    elif language in ['nodejs', 'node', 'javascript', 'js']:
        node_packages = get_node_packages()
        return node_packages

    return 'No packages found for the specified language. Sandbox only support nodejs and python.'
