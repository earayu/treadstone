"""
Shell MCP tools for command execution
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.core.service_container import services
from app.utils import normalize_cwd

from .app import mcp


if TYPE_CHECKING:
    from app.services.shell import OpenHandsShellManager


logger = logging.getLogger(__name__)

# Store the default session ID for automatic session management
_default_session_id: Optional[str] = None


async def _get_or_create_session(
    terminal_manager: 'OpenHandsShellManager', working_dir: Optional[str] = None
) -> str:
    """Get existing default session or create a new one."""
    global _default_session_id

    # Check if default session exists and is active
    if _default_session_id:
        session = terminal_manager.get_session(_default_session_id)
        if session and session.active:
            return _default_session_id

    # Create new default session
    session = await terminal_manager.create_session(working_dir=working_dir or '/tmp')
    _default_session_id = session.id
    return _default_session_id


@mcp.tool(structured_output=False)
async def execute_bash(
    cmd: str,
    cwd: Optional[str] = None,
    new_session: bool = False,
    timeout: Optional[int] = 30,
) -> Dict[str, Any]:
    """Execute a shell command. Sessions are managed automatically.

    Args:
        cmd: Shell command to execute
        cwd: Optional working directory (absolute path), default to '/tmp'
        new_session: If True, creates a new session instead of using the default
        timeout: Optional timeout in seconds for command execution (default: 30)

    Returns:
        Dict containing command, status, output, and exit_code
    """
    terminal_manager: 'OpenHandsShellManager' = services.get('terminal_manager')

    # Normalize working directory if provided
    working_dir = '/tmp'
    if cwd:
        working_dir = normalize_cwd(cwd)

    # Get or create session
    if new_session:
        session = await terminal_manager.create_session(working_dir=working_dir)
        session_id = session.id
    else:
        session_id = await _get_or_create_session(terminal_manager, working_dir)

    # Execute command
    result = await terminal_manager.execute_command(
        session_id, cmd, async_mode=False, timeout=timeout
    )

    return {
        'status': result.status.value,
        'output': result.output,
        'exit_code': result.exit_code,
    }
