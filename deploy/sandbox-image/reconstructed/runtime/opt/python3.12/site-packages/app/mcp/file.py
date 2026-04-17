"""
File MCP tools for file system operations and editing
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.core.service_container import services
from app.schemas.file import FileContentEncoding

from .app import mcp


if TYPE_CHECKING:
    from app.services.file import FileService

logger = logging.getLogger(__name__)


@mcp.tool(structured_output=False)
async def file_operations(
    action: str,
    path: str,
    content: Optional[str] = None,
    target: Optional[str] = None,
    pattern: Optional[str] = None,
    encoding: Optional[str] = 'utf-8',
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    append: bool = False,
    recursive: bool = False,
    show_hidden: bool = False,
    file_types: Optional[List[str]] = None,
    sudo: bool = False,
) -> Dict[str, Any]:
    """Unified file system operations tool for agents. `/tmp` and `/home/$USER` are fully accessible.

    Args:
        action: Operation type - "read", "write", "replace", "search", "find", "list"
        path: File or directory path
        content: Content for write/replace operations (or regex for search)
        target: Target string for replace operations (new_str)
        pattern: Pattern for find operations (glob syntax)
        encoding: File encoding (utf-8, base64, raw)
        start_line: Starting line for read operations (0-based)
        end_line: Ending line for read operations (not included)
        append: Append mode for write operations
        recursive: Recursive mode for find/list operations
        show_hidden: Show hidden files in list operations
        file_types: Filter by file extensions for list operations
        sudo: Use sudo privileges

    Returns:
        Dict containing operation result and relevant data
    """
    file_service: 'FileService' = services.get('file_service')

    try:
        if action == 'read':
            result = await file_service.read_file(
                file=path, start_line=start_line, end_line=end_line, sudo=sudo
            )
            return {
                'action': 'read',
                'path': path,
                'content': result.content,
                'success': True,
            }

        elif action == 'write':
            if content is None:
                raise ValueError('Content is required for write operation')

            result = await file_service.write_file(
                file=path,
                content=content,
                encoding=FileContentEncoding(encoding)
                if encoding in ['utf-8', 'base64', 'raw']
                else FileContentEncoding.UTF8,
                append=append,
                sudo=sudo,
            )
            return {
                'action': 'write',
                'path': path,
                'bytes_written': result.bytes_written,
                'success': True,
            }

        elif action == 'replace':
            if content is None or target is None:
                raise ValueError(
                    'Both content (old_str) and target (new_str) are required for replace operation'
                )

            result = await file_service.str_replace(
                file=path, old_str=content, new_str=target, sudo=sudo
            )
            return {
                'action': 'replace',
                'path': path,
                'replaced_count': result.replaced_count,
                'success': True,
            }

        elif action == 'search':
            if content is None:
                raise ValueError(
                    'Content (regex pattern) is required for search operation'
                )

            result = await file_service.find_in_content(
                file=path, regex=content, sudo=sudo
            )
            return {
                'action': 'search',
                'path': path,
                'matches': result.matches,
                'line_numbers': result.line_numbers,
                'match_count': len(result.matches),
                'success': True,
            }

        elif action == 'find':
            if pattern is None:
                raise ValueError('Pattern is required for find operation')

            result = await file_service.find_by_name(path=path, glob_pattern=pattern)
            return {
                'action': 'find',
                'path': path,
                'files': result.files,
                'file_count': len(result.files),
                'success': True,
            }

        elif action == 'list':
            result = await file_service.list_path(
                path=path,
                recursive=recursive,
                show_hidden=show_hidden,
                file_types=file_types,
                include_size=True,
                include_permissions=False,
                sort_by='name',
                sort_desc=False,
            )
            return {
                'action': 'list',
                'path': path,
                'files': [f.model_dump() for f in result.files],
                'total_count': result.total_count,
                'directory_count': result.directory_count,
                'file_count': result.file_count,
                'success': True,
            }

        else:
            raise ValueError(f'Unsupported action: {action}')

    except Exception as e:
        logger.error(f'File system operation failed: {str(e)}')
        return {'action': action, 'path': path, 'success': False, 'error': str(e)}


@mcp.tool(structured_output=False)
async def str_replace_editor(
    command: str,
    path: str,
    file_text: Optional[str] = None,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    insert_line: Optional[int] = None,
    view_range: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Professional file editor tool using openhands_aci editor.

    This tool provides advanced file editing capabilities compatible with Anthropic's
    str_replace_editor interface. Parameters and behavior match the standard interface.

    Args:
        command: Command to execute ("view", "create", "str_replace", "insert", "undo_edit")
        path: File path to operate on
        file_text: File content for create command
        old_str: Original string to replace (for str_replace command)
        new_str: New string to replace with (for str_replace and insert commands)
        insert_line: Line number to insert at (for insert command)
        view_range: Line range for view command [start, end]

    Returns:
        Dict containing editor operation result
    """
    file_service: 'FileService' = services.get('file_service')

    try:
        result = await file_service.str_replace_editor(
            command=command,
            path=path,
            file_text=file_text,
            old_str=old_str,
            new_str=new_str,
            insert_line=insert_line,
            view_range=view_range or [],
        )

        return {
            'command': command,
            'path': result.path,
            'output': result.output,
            'error': result.error,
            'prev_exist': result.prev_exist,
            'old_content': result.old_content,
            'new_content': result.new_content,
            'success': True,
        }

    except Exception as e:
        logger.error(f'str_replace_editor operation failed: {str(e)}')
        return {'command': command, 'path': path, 'success': False, 'error': str(e)}
