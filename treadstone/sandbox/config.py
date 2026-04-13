"""Sandbox module configuration view.

Read-only view exposing only the settings relevant to the sandbox domain.
New code within this module should import from here instead of the global
``treadstone.config.settings``.
"""

from treadstone.config import SANDBOX_STORAGE_SIZE_VALUES, settings

# Re-export the constant so sandbox code only needs this one import
__all__ = ["SANDBOX_STORAGE_SIZE_VALUES", "sandbox_settings"]


class _SandboxSettings:
    """Read-only proxy to the sandbox-related subset of global settings."""

    __slots__ = ()

    @property
    def namespace(self) -> str:
        return settings.sandbox_namespace

    @property
    def port(self) -> int:
        return settings.sandbox_port

    @property
    def storage_class(self) -> str:
        return settings.sandbox_storage_class

    @property
    def volume_snapshot_class(self) -> str:
        return settings.sandbox_volume_snapshot_class

    @property
    def default_storage_size(self) -> str:
        return settings.sandbox_default_storage_size

    @property
    def domain(self) -> str:
        return settings.sandbox_domain

    @property
    def subdomain_prefix(self) -> str:
        return settings.sandbox_subdomain_prefix

    @property
    def metering_enforcement_enabled(self) -> bool:
        return settings.metering_enforcement_enabled


sandbox_settings = _SandboxSettings()
