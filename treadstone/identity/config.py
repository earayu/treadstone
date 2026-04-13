"""Identity module configuration view.

Read-only view exposing only the settings relevant to authentication,
authorization, email verification, and password reset.  New code within
this module should import from here instead of the global
``treadstone.config.settings``.
"""

from treadstone.config import settings

__all__ = ["identity_settings"]


class _IdentitySettings:
    """Read-only proxy to the identity-related subset of global settings."""

    __slots__ = ()

    # ── App ──
    @property
    def app_base_url(self) -> str:
        return settings.app_base_url

    @property
    def debug(self) -> bool:
        return settings.debug

    # ── Auth ──
    @property
    def jwt_secret(self) -> str:
        return settings.jwt_secret

    @property
    def session_ttl_seconds(self) -> int:
        return settings.session_ttl_seconds

    # ── OAuth Social ──
    @property
    def google_oauth_client_id(self) -> str:
        return settings.google_oauth_client_id

    @property
    def google_oauth_client_secret(self) -> str:
        return settings.google_oauth_client_secret

    @property
    def github_oauth_client_id(self) -> str:
        return settings.github_oauth_client_id

    @property
    def github_oauth_client_secret(self) -> str:
        return settings.github_oauth_client_secret

    # ── Email ──
    @property
    def email_backend(self) -> str:
        return settings.email_backend

    @property
    def resend_api_key(self) -> str:
        return settings.resend_api_key

    @property
    def email_from(self) -> str:
        return settings.email_from

    @property
    def verification_token_lifetime_seconds(self) -> int:
        return settings.verification_token_lifetime_seconds

    @property
    def verification_resend_cooldown_seconds(self) -> int:
        return settings.verification_resend_cooldown_seconds

    @property
    def reset_password_token_lifetime_seconds(self) -> int:
        return settings.reset_password_token_lifetime_seconds

    @property
    def password_reset_request_cooldown_seconds(self) -> int:
        return settings.password_reset_request_cooldown_seconds

    @property
    def password_reset_ip_hourly_limit(self) -> int:
        return settings.password_reset_ip_hourly_limit

    # ── Sandbox domain (needed for auth redirects) ──
    @property
    def sandbox_domain(self) -> str:
        return settings.sandbox_domain

    @property
    def sandbox_subdomain_prefix(self) -> str:
        return settings.sandbox_subdomain_prefix


identity_settings = _IdentitySettings()
