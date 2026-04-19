"""
File operation related models
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class FileReadResult(BaseModel):
    """File read result"""

    content: str = Field(..., description='File content')
    file: str = Field(..., description='Path of the read file')


class FileWriteResult(BaseModel):
    """File write result"""

    file: str = Field(..., description='Path of the written file')
    bytes_written: Optional[int] = Field(None, description='Number of bytes written')


class FileReplaceResult(BaseModel):
    """File content replacement result"""

    file: str = Field(..., description='Path of the operated file')
    replaced_count: int = Field(0, description='Number of replacements')


class FileSearchResult(BaseModel):
    """File content search result"""

    file: str = Field(..., description='Path of the searched file')
    matches: List[str] = Field([], description='List of matched content')
    line_numbers: List[int] = Field([], description='List of matched line numbers')


class FileFindResult(BaseModel):
    """File find result"""

    path: str = Field(..., description='Path of the search directory')
    files: List[str] = Field([], description='List of found files')


class FileUploadResult(BaseModel):
    """File upload result"""

    file_path: str = Field(..., description='Path of the uploaded file')
    file_size: int = Field(..., description='Size of the uploaded file in bytes')
    success: bool = Field(..., description='Whether upload was successful')


class FileInfo(BaseModel):
    """File information"""

    name: str = Field(..., description='File name')
    path: str = Field(..., description='Full file path')
    is_directory: bool = Field(..., description="Whether it's a directory")
    size: Optional[int] = Field(None, description='File size in bytes')
    modified_time: Optional[str] = Field(
        None, description='Last modified time (ISO format)'
    )
    permissions: Optional[str] = Field(None, description='File permissions')
    extension: Optional[str] = Field(None, description='File extension')


class FileListResult(BaseModel):
    """File list result"""

    path: str = Field(..., description='Listed directory path')
    files: List[FileInfo] = Field([], description='List of files and directories')
    total_count: int = Field(0, description='Total number of items')
    directory_count: int = Field(0, description='Number of directories')
    file_count: int = Field(0, description='Number of files')


class StrReplaceEditorResult(BaseModel):
    """String replace editor result based on openhands_aci CLIResult"""

    output: str = Field(..., description='Command execution output')
    error: Optional[str] = Field(None, description='Error message if any')
    path: str = Field(..., description='File path that was operated on')
    prev_exist: bool = Field(
        ..., description='Whether the file existed before operation'
    )
    old_content: Optional[str] = Field(None, description='Previous file content')
    new_content: Optional[str] = Field(
        None, description='New file content after operation'
    )
