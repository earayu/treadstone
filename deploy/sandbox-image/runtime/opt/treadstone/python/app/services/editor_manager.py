"""
Editor Manager for maintaining OHEditor instances across requests.

This module provides a singleton EditorManager that maintains OHEditor instances
for each file path, allowing edit history to persist across API requests.
"""

import asyncio
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Dict, Optional


if TYPE_CHECKING:
    from vendors.openhands_aci.editor.editor import OHEditor


def get_oh_editor():
    from vendors.openhands_aci.editor.editor import OHEditor

    return OHEditor


class EditorManager:
    """
    Singleton manager for OHEditor instances.

    Maintains a cache of OHEditor instances per file path to preserve
    edit history across multiple API requests.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Ensure only one instance of EditorManager exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the editor manager."""
        if self._initialized:
            return

        self._editors: Dict[str, OHEditor] = {}
        self._access_lock = asyncio.Lock()
        self._initialized = True

    async def get_editor(
        self, file_path: str, workspace_root: Optional[str] = None
    ) -> 'OHEditor':
        """
        Get or create an OHEditor instance for the given file path.

        Args:
            file_path: The path of the file to edit
            workspace_root: Optional workspace root directory

        Returns:
            An OHEditor instance with preserved history for the file
        """
        async with self._access_lock:
            # Normalize the path
            normalized_path = str(Path(file_path).resolve())

            # Check if we have an existing editor for this path
            if normalized_path in self._editors:
                return self._editors[normalized_path]

            # Create a new editor
            editor = get_oh_editor()(workspace_root=workspace_root)
            self._editors[normalized_path] = editor
            return editor

    async def clear_editor(self, file_path: str):
        """
        Clear the editor instance for a specific file.

        Args:
            file_path: The path of the file whose editor should be cleared
        """
        async with self._access_lock:
            normalized_path = str(Path(file_path).resolve())
            if normalized_path in self._editors:
                del self._editors[normalized_path]

    async def clear_all(self):
        """Clear all cached editor instances."""
        async with self._access_lock:
            self._editors.clear()

    def get_cached_count(self) -> int:
        """Get the number of cached editor instances."""
        return len(self._editors)


# Global singleton instance
editor_manager = EditorManager()
