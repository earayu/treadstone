"""
业务模型定义
"""

from app.models.shell import (
    ShellCommandResult,
    ShellViewResult,
    ShellWaitResult,
    ShellWriteResult,
    ShellKillResult,
)
from app.models.file import (
    FileReadResult,
    FileWriteResult,
    FileReplaceResult,
    FileSearchResult,
    FileFindResult,
)

__all__ = [
    'ShellCommandResult',
    'ShellViewResult',
    'ShellWaitResult',
    'ShellWriteResult',
    'ShellKillResult',
    'FileReadResult',
    'FileWriteResult',
    'FileReplaceResult',
    'FileSearchResult',
    'FileFindResult',
]
