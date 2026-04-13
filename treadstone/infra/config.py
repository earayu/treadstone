"""Infra module configuration view.

Read-only view exposing only the settings relevant to the K8s
infrastructure layer.  New code within this module should import from here
instead of the global ``treadstone.config.settings``.
"""

from treadstone.config import settings

__all__ = ["infra_settings"]


class _InfraSettings:
    """Read-only proxy to the infra-related subset of global settings."""

    __slots__ = ()

    @property
    def sandbox_namespace(self) -> str:
        return settings.sandbox_namespace


infra_settings = _InfraSettings()
