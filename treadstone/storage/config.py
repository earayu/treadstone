"""Storage module configuration view.

Read-only view exposing only the settings relevant to storage backends
and volume snapshots.  New code within this module should import from here
instead of the global ``treadstone.config.settings``.
"""

from treadstone.config import settings

__all__ = ["storage_settings"]


class _StorageSettings:
    """Read-only proxy to the storage-related subset of global settings."""

    __slots__ = ()

    @property
    def sandbox_port(self) -> int:
        return settings.sandbox_port

    @property
    def storage_class(self) -> str:
        return settings.sandbox_storage_class

    @property
    def volume_snapshot_class(self) -> str:
        return settings.sandbox_volume_snapshot_class


storage_settings = _StorageSettings()
