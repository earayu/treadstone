"""Proxy module configuration view.

Read-only view exposing only the settings relevant to sandbox proxy
routing, subdomain middleware, and upstream connectivity.  New code within
this module should import from here instead of the global
``treadstone.config.settings``.
"""

from treadstone.config import settings

__all__ = ["proxy_settings"]


class _ProxySettings:
    """Read-only proxy to the proxy-related subset of global settings."""

    __slots__ = ()

    @property
    def app_base_url(self) -> str:
        return settings.app_base_url

    @property
    def debug(self) -> bool:
        return settings.debug

    @property
    def sandbox_domain(self) -> str:
        return settings.sandbox_domain

    @property
    def sandbox_namespace(self) -> str:
        return settings.sandbox_namespace

    @property
    def sandbox_port(self) -> int:
        return settings.sandbox_port

    @property
    def sandbox_proxy_timeout(self) -> float:
        return settings.sandbox_proxy_timeout

    @property
    def sandbox_subdomain_prefix(self) -> str:
        return settings.sandbox_subdomain_prefix


proxy_settings = _ProxySettings()
