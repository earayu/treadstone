"""
File operation request models
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FileReadRequest(BaseModel):
    """File read request"""

    file: str = Field(..., description='Absolute file path')
    start_line: Optional[int] = Field(None, description='Start line (0-based)')
    end_line: Optional[int] = Field(None, description='End line (not inclusive)')
    sudo: Optional[bool] = Field(False, description='Whether to use sudo privileges')


class FileContentEncoding(str, Enum):
    """File content encoding type"""

    UTF8 = 'utf-8'
    BASE64 = 'base64'
    RAW = 'raw'


class FileWriteRequest(BaseModel):
    """File write request - supports both text and binary content"""

    file: str = Field(..., description='Absolute file path')
    content: str = Field(
        ..., description='Content to write (text or base64 encoded for binary)'
    )
    encoding: Optional[FileContentEncoding] = Field(
        FileContentEncoding.UTF8,
        description='Content encoding: utf-8 for text, base64 for binary data',
    )
    append: Optional[bool] = Field(False, description='Whether to use append mode')
    leading_newline: Optional[bool] = Field(
        False, description='Whether to add leading newline (only for text mode)'
    )
    trailing_newline: Optional[bool] = Field(
        False, description='Whether to add trailing newline (only for text mode)'
    )
    sudo: Optional[bool] = Field(False, description='Whether to use sudo privileges')


class FileReplaceRequest(BaseModel):
    """File content replacement request"""

    file: str = Field(..., description='Absolute file path')
    old_str: str = Field(..., description='Original string to replace')
    new_str: str = Field(..., description='New string to replace with')
    sudo: Optional[bool] = Field(False, description='Whether to use sudo privileges')


class FileSearchRequest(BaseModel):
    """File content search request"""

    file: str = Field(..., description='Absolute file path')
    regex: str = Field(..., description='Regular expression pattern')
    sudo: Optional[bool] = Field(False, description='Whether to use sudo privileges')


class FileFindRequest(BaseModel):
    """File find request"""

    path: str = Field(..., description='Directory path to search')
    glob: str = Field(..., description='Filename pattern (glob syntax)')


class FileListRequest(BaseModel):
    """File list request"""

    path: str = Field(..., description='Directory path to list')
    recursive: Optional[bool] = Field(False, description='Whether to list recursively')
    show_hidden: Optional[bool] = Field(
        True, description='Whether to show hidden files'
    )
    file_types: Optional[list[str]] = Field(
        None, description="Filter by file extensions (e.g., ['.py', '.txt'])"
    )
    max_depth: Optional[int] = Field(
        None, description='Maximum depth for recursive listing'
    )
    include_size: Optional[bool] = Field(
        True, description='Whether to include file size information'
    )
    include_permissions: Optional[bool] = Field(
        False, description='Whether to include file permissions'
    )
    sort_by: Optional[str] = Field(
        'name', description='Sort by: name, size, modified, type'
    )
    sort_desc: Optional[bool] = Field(False, description='Sort in descending order')


class StrReplaceEditorRequest(BaseModel):
    """String replace editor request based on openhands_aci"""

    command: Literal[
        'view',
        'create',
        'str_replace',
        'insert',
        'undo_edit',
    ] = Field(
        ...,
        description='The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.',
    )

    path: str = Field(
        ...,
        description='Absolute path to file or directory, e.g. `/workspace/file.py` or `/workspace`.',
    )
    file_text: Optional[str] = Field(
        None,
        description='Required parameter of `create` command, with the content of the file to be created.',
    )
    old_str: Optional[str] = Field(
        None,
        description='Required parameter of `str_replace` command containing the string in `path` to replace.',
    )
    new_str: Optional[str] = Field(
        None,
        description='Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.',
    )
    insert_line: Optional[int] = Field(
        None,
        description='Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.',
    )
    view_range: Optional[list[int]] = Field(
        [],
        description='Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.',
    )
