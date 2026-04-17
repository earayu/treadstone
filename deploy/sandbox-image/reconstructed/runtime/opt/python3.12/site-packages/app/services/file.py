"""
File Operation Service Implementation - Async Version
"""

import asyncio
import base64
import glob
import os
import re
import stat
from typing import Optional, Union

from fastapi import UploadFile

from app.core.exceptions import (
    AppException,
    BadRequestException,
    ResourceNotFoundException,
)
from app.models.file import (
    FileFindResult,
    FileInfo,
    FileListResult,
    FileReadResult,
    FileReplaceResult,
    FileSearchResult,
    FileUploadResult,
    FileWriteResult,
    StrReplaceEditorResult,
)
from app.schemas.file import FileContentEncoding
from app.services.editor_manager import editor_manager


class FileService:
    """File Operation Service"""

    async def read_file(
        self,
        file: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        sudo: bool = False,
    ) -> FileReadResult:
        """
        Asynchronously read file content

        Args:
            file: Absolute file path
            start_line: Starting line (0-based)
            end_line: Ending line (not included)
            sudo: Whether to use sudo privileges
        """
        # Check if file exists
        if not os.path.exists(file) and not sudo:
            raise ResourceNotFoundException(f'File does not exist: {file}')

        try:
            content = ''

            # Read with sudo
            if sudo:
                command = f"sudo cat '{file}'"
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    raise BadRequestException(f'Failed to read file: {stderr.decode()}')

                content = stdout.decode('utf-8')
            else:
                # Asynchronously read file
                def read_file_async():
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            return f.read()
                    except Exception as e:
                        raise AppException(message=f'Failed to read file: {str(e)}')

                # Execute IO operation in thread pool
                content = await asyncio.to_thread(read_file_async)

            # Process line range
            if start_line is not None or end_line is not None:
                lines = content.splitlines()
                start = start_line if start_line is not None else 0
                end = end_line if end_line is not None else len(lines)
                content = '\n'.join(lines[start:end])

            return FileReadResult(content=content, file=file)
        except Exception as e:
            if isinstance(e, BadRequestException) or isinstance(
                e, ResourceNotFoundException
            ):
                raise e
            raise AppException(message=f'Failed to read file: {str(e)}')

    async def write_file(
        self,
        file: str,
        content: str,
        encoding: Optional[Union[FileContentEncoding, str]] = FileContentEncoding.UTF8,
        append: bool = False,
        leading_newline: bool = False,
        trailing_newline: bool = False,
        sudo: bool = False,
    ) -> FileWriteResult:
        """
        Asynchronously write file content (supports both text and binary)

        Args:
            file: Absolute file path
            content: Content to write (text or base64 encoded for binary)
            encoding: Content encoding type (utf-8, base64, or raw)
            append: Whether to append mode
            leading_newline: Whether to add a leading newline (only for text mode)
            trailing_newline: Whether to add a trailing newline (only for text mode)
            sudo: Whether to use sudo privileges
        """
        try:
            # Convert encoding to string if it's an enum
            if isinstance(encoding, FileContentEncoding):
                encoding = encoding.value

            # Prepare content based on encoding
            if encoding == FileContentEncoding.BASE64.value:
                # Decode base64 to bytes
                try:
                    file_bytes = base64.b64decode(content)
                    is_binary = True
                except Exception as e:
                    raise BadRequestException(f'Invalid base64 content: {str(e)}')
            elif encoding == FileContentEncoding.RAW.value:
                # Raw bytes mode
                file_bytes = content.encode(
                    'latin-1'
                )  # Use latin-1 to preserve byte values
                is_binary = True
            else:
                # Text mode (UTF-8)
                is_binary = False
                # Add newlines only in text mode
                if leading_newline:
                    content = '\n' + content
                if trailing_newline:
                    content = content + '\n'
                file_bytes = content.encode('utf-8')

            bytes_written = 0

            # Write with sudo
            if sudo:
                mode = '>>' if append else '>'
                # Create temporary file
                temp_file = f'/tmp/file_write_{os.getpid()}.tmp'

                # Asynchronously write to temporary file
                def write_temp_file():
                    if is_binary:
                        with open(temp_file, 'wb') as f:
                            f.write(file_bytes)
                    else:
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                    return len(file_bytes)

                bytes_written = await asyncio.to_thread(write_temp_file)

                # Use sudo to write temporary file content to target file
                command = f'sudo bash -c "cat {temp_file} {mode} \'{file}\'"'
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    raise BadRequestException(
                        f'Failed to write file: {stderr.decode()}'
                    )

                # Clean up temporary file
                os.unlink(temp_file)
            else:
                # Ensure directory exists
                os.makedirs(os.path.dirname(file), exist_ok=True)

                # Asynchronously write file
                def write_file_async():
                    if is_binary:
                        mode = 'ab' if append else 'wb'
                        with open(file, mode) as f:
                            f.write(file_bytes)
                            return len(file_bytes)
                    else:
                        mode = 'a' if append else 'w'
                        with open(file, mode, encoding='utf-8') as f:
                            f.write(content)
                            return len(file_bytes)

                bytes_written = await asyncio.to_thread(write_file_async)

            return FileWriteResult(file=file, bytes_written=bytes_written)
        except Exception as e:
            if isinstance(e, BadRequestException):
                raise e
            raise AppException(message=f'Failed to write file: {str(e)}')

    async def str_replace(
        self, file: str, old_str: str, new_str: str, sudo: bool = False
    ) -> FileReplaceResult:
        """
        Asynchronously replace string in file

        Args:
            file: Absolute file path
            old_str: Original string to be replaced
            new_str: New replacement string
            sudo: Whether to use sudo privileges
        """
        # First read file content
        file_result = await self.read_file(file, sudo=sudo)
        content = file_result.content

        # Calculate replacement count
        replaced_count = content.count(old_str)
        if replaced_count == 0:
            return FileReplaceResult(file=file, replaced_count=0)

        # Perform replacement
        new_content = content.replace(old_str, new_str)

        # Write back to file
        await self.write_file(file, new_content, sudo=sudo)

        return FileReplaceResult(file=file, replaced_count=replaced_count)

    async def find_in_content(
        self, file: str, regex: str, sudo: bool = False
    ) -> FileSearchResult:
        """
        Asynchronously search in file content

        Args:
            file: Absolute file path
            regex: Regular expression pattern
            sudo: Whether to use sudo privileges
        """
        # Read file
        file_result = await self.read_file(file, sudo=sudo)
        content = file_result.content

        # Process line by line
        lines = content.splitlines()
        matches = []
        line_numbers = []

        # Compile regular expression
        try:
            pattern = re.compile(regex)
        except Exception as e:
            raise BadRequestException(f'Invalid regular expression: {str(e)}')

        # Find matches (use async processing for possibly large files)
        def process_lines():
            nonlocal matches, line_numbers
            for i, line in enumerate(lines):
                if pattern.search(line):
                    matches.append(line)
                    line_numbers.append(i)

        await asyncio.to_thread(process_lines)

        return FileSearchResult(file=file, matches=matches, line_numbers=line_numbers)

    async def find_by_name(self, path: str, glob_pattern: str) -> FileFindResult:
        """
        Asynchronously find files by name pattern

        Args:
            path: Directory path to search
            glob_pattern: File name pattern (glob syntax)
        """
        # Check if path exists
        if not os.path.exists(path):
            raise ResourceNotFoundException(f'Directory does not exist: {path}')

        # Asynchronously find files
        def glob_async():
            search_pattern = os.path.join(path, glob_pattern)
            return glob.glob(search_pattern, recursive=True)

        files = await asyncio.to_thread(glob_async)

        return FileFindResult(path=path, files=files)

    async def upload_file(self, path: str, file_stream: UploadFile) -> FileUploadResult:
        """
        Upload file using streaming for large files

        Args:
            path: Target file path to save uploaded file
            file_stream: File stream from FastAPI UploadFile
        """
        try:
            chunk_size = 8192  # 8KB chunks
            total_size = 0

            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)

            # Stream write directly to target file
            def write_stream_direct():
                nonlocal total_size
                with open(path, 'wb') as f:
                    while True:
                        chunk = file_stream.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        total_size += len(chunk)

            await asyncio.to_thread(write_stream_direct)

            return FileUploadResult(file_path=path, file_size=total_size, success=True)
        except Exception as e:
            raise AppException(message=f'Failed to upload file: {str(e)}')

    def ensure_file(self, path: str) -> None:
        """
        Ensure file exists

        Args:
            path: Path of the file to check
        """
        try:
            # Check if file exists
            if not os.path.exists(path):
                raise ResourceNotFoundException(f'File does not exist: {path}')

        except Exception as e:
            if isinstance(e, (BadRequestException, ResourceNotFoundException)):
                raise e
            raise AppException(message=f'Failed to ensure file: {str(e)}')

    async def list_path(
        self,
        path: str,
        recursive: bool = False,
        show_hidden: bool = False,
        file_types: Optional[list[str]] = None,
        max_depth: Optional[int] = None,
        include_size: bool = True,
        include_permissions: bool = False,
        sort_by: str = 'name',
        sort_desc: bool = False,
        max_files: Optional[int] = 10000,  # Prevent memory issues
    ) -> FileListResult:
        """
        Asynchronously list path contents with flexible options

        Args:
            path: Path to list (directory or file)
            recursive: Whether to list recursively
            show_hidden: Whether to show hidden files
            file_types: Filter by file extensions (e.g., ['.py', '.txt'])
            max_depth: Maximum depth for recursive listing
            include_size: Whether to include file size information
            include_permissions: Whether to include file permissions
            sort_by: Sort by: name, size, modified, type
            sort_desc: Sort in descending order
            max_files: Maximum number of files to process (default: 10000)
        """
        # Check if path exists
        if not os.path.exists(path):
            raise ResourceNotFoundException(f'Directory does not exist: {path}')

        if not os.path.isdir(path):
            raise BadRequestException(f'Path is not a directory: {path}')

        # Normalize file types for faster comparison
        # Accept both 'py' and '.py' formats, normalize to '.py'
        normalized_file_types = None
        if file_types:
            normalized_file_types = set()
            for ft in file_types:
                ft_lower = ft.lower()
                # Add dot prefix if not present
                if not ft_lower.startswith('.'):
                    ft_lower = '.' + ft_lower
                normalized_file_types.add(ft_lower)

        def list_files():
            files = []
            file_count = 0

            def process_directory(current_path: str, current_depth: int = 0):
                nonlocal file_count

                if max_depth is not None and current_depth > max_depth:
                    return

                if max_files and file_count >= max_files:
                    return

                try:
                    dir_entries = os.scandir(current_path)

                    for entry in dir_entries:
                        # Early termination check
                        if max_files and file_count >= max_files:
                            dir_entries.close()
                            return

                        # Skip hidden files if not requested
                        if not show_hidden and entry.name.startswith('.'):
                            continue

                        # Early file type filtering (before stat)
                        if normalized_file_types and not entry.is_dir():
                            _, ext = os.path.splitext(entry.name)
                            if ext.lower() not in normalized_file_types:
                                continue

                        try:
                            # Use scandir's cached stat info when possible
                            file_stat = entry.stat()
                            is_directory = entry.is_dir()

                            # Create file info with minimal operations
                            file_info = FileInfo(
                                name=entry.name,
                                path=entry.path,
                                is_directory=is_directory,
                                size=(
                                    file_stat.st_size
                                    if include_size and not is_directory
                                    else None
                                ),
                                modified_time=(
                                    str(int(file_stat.st_mtime))
                                    if include_size
                                    else None
                                ),
                                permissions=(
                                    stat.filemode(file_stat.st_mode)
                                    if include_permissions
                                    else None
                                ),
                                extension=(
                                    os.path.splitext(entry.name)[1]
                                    if not is_directory
                                    else None
                                ),
                            )

                            files.append(file_info)
                            file_count += 1

                            # Recursively process subdirectories
                            if recursive and is_directory:
                                process_directory(entry.path, current_depth + 1)

                        except (OSError, PermissionError):
                            # Skip files that can't be accessed
                            continue

                    dir_entries.close()

                except (OSError, PermissionError):
                    # Skip directories that can't be accessed
                    pass

            process_directory(path)
            return files

        # Execute file listing - use thread pool only for large operations
        if recursive or (max_files and max_files > 1000):
            files = await asyncio.to_thread(list_files)
        else:
            files = list_files()

        # Sort files
        def sort_key(file_info: FileInfo):
            if sort_by == 'name':
                return file_info.name.lower()
            elif sort_by == 'size':
                return file_info.size or 0
            elif sort_by == 'modified':
                return file_info.modified_time or ''
            elif sort_by == 'type':
                return (0 if file_info.is_directory else 1, file_info.name.lower())
            else:
                return file_info.name.lower()

        files.sort(key=sort_key, reverse=sort_desc)

        # Calculate statistics
        total_count = len(files)
        directory_count = sum(1 for f in files if f.is_directory)
        file_count = total_count - directory_count

        return FileListResult(
            path=path,
            files=files,
            total_count=total_count,
            directory_count=directory_count,
            file_count=file_count,
        )

    async def str_replace_editor(
        self,
        command: str,
        path: str,
        file_text: Optional[str] = None,
        old_str: Optional[str] = None,
        new_str: Optional[str] = None,
        insert_line: Optional[int] = None,
        view_range: Optional[list[int]] = [],
    ) -> StrReplaceEditorResult:
        """
        使用 openhands_aci 编辑器执行文件操作

        Args:
            command: 要执行的命令 (view, create, str_replace, insert, undo_edit)
            path: 文件路径
            file_text: create 命令需要的文件内容
            old_str: str_replace 命令需要的原字符串
            new_str: str_replace 和 insert 命令需要的新字符串
            insert_line: insert 命令需要的插入行号
            view_range: view 命令的可选行范围
        """
        try:
            from openhands_aci.editor.exceptions import ToolError

            editor = await editor_manager.get_editor(path)

            # 准备参数
            kwargs = {}
            if file_text is not None:
                kwargs['file_text'] = file_text
            if old_str is not None:
                kwargs['old_str'] = old_str
            if new_str is not None:
                kwargs['new_str'] = new_str
            if insert_line is not None:
                kwargs['insert_line'] = insert_line
            if len(view_range) > 0:
                kwargs['view_range'] = view_range

            # 在线程池中执行编辑器操作
            def run_editor():
                return editor(command=command, path=path, **kwargs)

            # 异步执行编辑器操作
            result = await asyncio.to_thread(run_editor)

            # 转换结果为我们的模型
            return StrReplaceEditorResult(
                output=result.output,
                error=getattr(result, 'error', None),
                path=result.path,
                prev_exist=result.prev_exist,
                old_content=getattr(result, 'old_content', None),
                new_content=getattr(result, 'new_content', None),
            )

        except ToolError as e:
            # Categorize ToolError based on the error message
            error_msg = str(e)
            if any(
                keyword in error_msg.lower()
                for keyword in ['missing', 'parameter', 'required']
            ):
                raise BadRequestException(message=error_msg)
            elif any(
                keyword in error_msg.lower()
                for keyword in ['invalid', 'not found', 'does not exist', 'nonexistent']
            ):
                raise BadRequestException(message=error_msg)
            elif any(
                keyword in error_msg.lower()
                for keyword in [
                    'multiple occurrences',
                    'no replacement',
                    'must be different',
                ]
            ):
                raise BadRequestException(message=error_msg)
            elif any(
                keyword in error_msg.lower()
                for keyword in ['no edit history', 'history found', 'undo']
            ):
                raise BadRequestException(message=error_msg)
            else:
                raise AppException(message=f'[str_replace_editor] error: {error_msg}')
        except Exception as e:
            raise AppException(message=f'[str_replace_editor] error: {str(e)}')
