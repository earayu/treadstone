"""
File operation API interfaces
"""

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.core.service_container import services
from app.models.file import (
    FileFindResult,
    FileListResult,
    FileReadResult,
    FileReplaceResult,
    FileSearchResult,
    FileUploadResult,
    FileWriteResult,
    StrReplaceEditorResult,
)
from app.schemas.file import (
    FileFindRequest,
    FileListRequest,
    FileReadRequest,
    FileReplaceRequest,
    FileSearchRequest,
    FileWriteRequest,
    StrReplaceEditorRequest,
)
from app.schemas.response import Response


if TYPE_CHECKING:
    from app.services.file import FileService


router = APIRouter()

logger = logging.getLogger(__name__)


@router.post(
    '/read',
    response_model=Response[FileReadResult],
    operation_id='read_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'read_file',
    },
)
async def read_file(request: FileReadRequest):
    """
    Read file content
    """
    file_service: 'FileService' = services.get('file_service')
    result = await file_service.read_file(
        file=request.file,
        start_line=request.start_line,
        end_line=request.end_line,
        sudo=request.sudo,
    )

    # Construct response
    return Response(
        success=True, message='File read successfully', data=result.model_dump()
    )


@router.post(
    '/write',
    response_model=Response[FileWriteResult],
    operation_id='write_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'write_file',
    },
)
async def write_file(
    request: FileWriteRequest,
):
    """
    Write file content (supports both text and binary files)

    For binary files, set encoding to 'base64' and provide base64-encoded content.
    For text files, use default 'utf-8' encoding.
    """
    file_service: 'FileService' = services.get('file_service')

    result = await file_service.write_file(
        file=request.file,
        content=request.content,
        encoding=request.encoding,
        append=request.append,
        leading_newline=request.leading_newline,
        trailing_newline=request.trailing_newline,
        sudo=request.sudo,
    )

    # Construct response
    return Response(
        success=True, message='File written successfully', data=result.model_dump()
    )


@router.post(
    '/replace',
    response_model=Response[FileReplaceResult],
    operation_id='replace_in_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'replace_in_file',
    },
)
async def replace_in_file(request: FileReplaceRequest):
    """
    Replace string in file
    """
    file_service: 'FileService' = services.get('file_service')
    result = await file_service.str_replace(
        file=request.file,
        old_str=request.old_str,
        new_str=request.new_str,
        sudo=request.sudo,
    )

    # Construct response
    return Response(
        success=True,
        message=f'Replacement completed, replaced {result.replaced_count} occurrences',
        data=result.model_dump(),
    )


@router.post(
    '/search',
    response_model=Response[FileSearchResult],
    operation_id='search_in_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'search_in_file',
    },
)
async def search_in_file(request: FileSearchRequest):
    """
    Search in file content
    """
    file_service: 'FileService' = services.get('file_service')
    result = await file_service.find_in_content(
        file=request.file, regex=request.regex, sudo=request.sudo
    )

    # Construct response
    return Response(
        success=True,
        message=f'Search completed, found {len(result.matches)} matches',
        data=result.model_dump(),
    )


@router.post(
    '/find',
    response_model=Response[FileFindResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'find_files',
    },
)
async def find_files(request: FileFindRequest):
    """
    Find files by name pattern
    """
    file_service: 'FileService' = services.get('file_service')
    result = await file_service.find_by_name(
        path=request.path, glob_pattern=request.glob
    )

    # Construct response
    return Response(
        success=True,
        message=f'Search completed, found {len(result.files)} files',
        data=result.model_dump(),
    )


@router.post(
    '/upload',
    response_model=Response[FileUploadResult],
    operation_id='upload_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'upload_file',
    },
)
async def upload_file(file: UploadFile = File(...), path: str = Form(None)):
    """
    Upload file using streaming
    """
    file_service: 'FileService' = services.get('file_service')
    if not path:
        path = f'/tmp/{file.filename}'

    result = await file_service.upload_file(path=path, file_stream=file)

    return Response(
        success=True, message='File uploaded successfully', data=result.model_dump()
    )


@router.get(
    '/download',
    response_class=FileResponse,
    responses={
        200: {
            'content': {
                'application/octet-stream': {
                    'schema': {'type': 'string', 'format': 'binary'}
                }
            }
        }
    },
    operation_id='download_file',
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'download_file',
    },
)
async def download_file(path: str) -> FileResponse:
    """
    Download file using FileResponse
    """
    file_service: 'FileService' = services.get('file_service')
    # Check if file exists (this will raise appropriate exception if not found)
    file_service.ensure_file(path)

    # Determine filename from path
    filename = path.split('/')[-1]

    return FileResponse(
        path=path, filename=filename, media_type='application/octet-stream'
    )


@router.post(
    '/list',
    response_model=Response[FileListResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'list_path',
    },
)
async def list_path(request: FileListRequest):
    """
    List path contents with flexible options
    """
    file_service: 'FileService' = services.get('file_service')

    logger.info(f'ListPath request: {request.model_dump()}')

    result = await file_service.list_path(
        path=request.path,
        recursive=request.recursive,
        show_hidden=request.show_hidden,
        file_types=request.file_types,
        max_depth=request.max_depth,
        include_size=request.include_size,
        include_permissions=request.include_permissions,
        sort_by=request.sort_by,
        sort_desc=request.sort_desc,
    )

    # Construct response
    return Response(
        success=True,
        message=f'Path listed successfully, found {result.total_count} items',
        data=result.model_dump(),
    )


@router.post(
    '/str_replace_editor',
    response_model=Response[StrReplaceEditorResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'file',
        'x-fern-sdk-method-name': 'str_replace_editor',
    },
)
async def str_replace_editor(request: StrReplaceEditorRequest):
    """
    An filesystem editor tool that allows the agent to
    - view
    - create
    - navigate
    - edit files
    The tool parameters are defined by Anthropic and are not editable.
    """
    file_service: 'FileService' = services.get('file_service')

    logger.info(f'StrReplaceEditor request: {request.model_dump()}')

    result = await file_service.str_replace_editor(
        command=request.command,
        path=request.path,
        file_text=request.file_text,
        old_str=request.old_str,
        new_str=request.new_str,
        insert_line=request.insert_line,
        view_range=request.view_range,
    )

    return Response(
        success=True,
        message=f"StrReplaceEditor successfully executed command '{request.command}'",
        data=result.model_dump(),
    )
