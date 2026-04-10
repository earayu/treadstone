import logging
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "CHANGE_ME_IN_PROD"
_MIN_JWT_SECRET_LENGTH = 32
_UNSUPPORTED_OIDC_AUTH_TYPES = {"auth0", "authing", "logto"}
SANDBOX_STORAGE_SIZE_VALUES = ("5Gi", "10Gi", "20Gi")


class Settings(BaseSettings):
    app_name: str = "treadstone"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/treadstone?sslmode=require"
    # Public web-app origin used for browser auth flows (OAuth callbacks, sandbox
    # bootstrap redirects, CLI browser login).  In production this should point to
    # the frontend domain (e.g. https://app.treadstone-ai.dev) whose nginx reverse-
    # proxies /v1/ to the backend, so that cookies stay on a single host.
    app_base_url: str = "http://localhost"

    # Auth
    auth_type: str = "cookie"  # cookie | auth0 | authing | logto | none
    jwt_secret: str = _DEFAULT_JWT_SECRET
    session_ttl_seconds: int = 604800

    # OAuth Social
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    # Auth0 / Authing / Logto
    auth0_domain: str = ""
    auth0_client_id: str = ""
    authing_domain: str = ""
    authing_app_id: str = ""
    logto_domain: str = ""
    logto_app_id: str = ""

    # Email verification
    email_backend: Literal["resend", "memory"] = "memory"
    resend_api_key: str = ""
    email_from: str = "support@treadstone-ai.dev"
    verification_token_lifetime_seconds: int = 3600
    verification_resend_cooldown_seconds: int = 60
    reset_password_token_lifetime_seconds: int = 3600
    password_reset_request_cooldown_seconds: int = 60
    password_reset_ip_hourly_limit: int = 5

    # Sandbox proxy defaults (overridable per-request via X-Sandbox-* headers)
    sandbox_namespace: str = "treadstone-local"
    sandbox_port: int = 8080
    sandbox_proxy_timeout: float = 180.0
    sandbox_storage_class: str = "treadstone-workspace"
    sandbox_volume_snapshot_class: str = "treadstone-workspace-snapshot"
    sandbox_default_storage_size: Literal["5Gi", "10Gi", "20Gi"] = "5Gi"

    # Metering — enforcement (quota checks) can be disabled independently of recording
    metering_enforcement_enabled: bool = False

    # Leader election for singleton background sync tasks in multi-replica deploys
    leader_election_enabled: bool = False
    leader_election_lease_name: str = "treadstone-sync-leader"
    leader_election_lease_duration_seconds: int = 15
    leader_election_renew_interval_seconds: int = 5
    leader_election_retry_interval_seconds: int = 2
    pod_name: str = ""
    pod_namespace: str = ""

    # CORS — allowed origins for the Web UI frontend.
    # Default includes the Vite dev server; override in production env files.
    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    # Subdomain-based sandbox routing (for browser Web UI access)
    # Dev: "sandbox.localhost"  →  sandbox-{sandbox_id}.sandbox.localhost[:port]
    # Prod: "treadstone-ai.dev" →  sandbox-{sandbox_id}.treadstone-ai.dev
    # Empty string disables subdomain routing.
    sandbox_domain: str = ""

    # Only subdomains starting with this prefix are treated as sandbox Web UI
    # traffic.  Non-matching subdomains (api, www, docs, …) pass through to
    # the normal FastAPI app.  Override via TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX.
    sandbox_subdomain_prefix: str = "sandbox-"

    model_config = {
        "env_prefix": "TREADSTONE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()


def is_local_sandbox_domain(domain: str) -> bool:
    host = domain.strip().lower()
    return host == "localhost" or host.endswith(".localhost")


def is_local_hostname(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().lower()
    return normalized in {"localhost", "127.0.0.1", "::1"} or normalized.endswith(".localhost")


def validate_runtime_settings(cfg: Settings) -> None:
    if cfg.jwt_secret == _DEFAULT_JWT_SECRET or len(cfg.jwt_secret) < _MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(
            "TREADSTONE_JWT_SECRET must be set to a non-default value at least "
            f"{_MIN_JWT_SECRET_LENGTH} characters long."
        )

    if cfg.auth_type in _UNSUPPORTED_OIDC_AUTH_TYPES:
        raise RuntimeError(
            f"TREADSTONE_AUTH_TYPE={cfg.auth_type!r} is not supported yet. "
            "External OIDC bearer auth is disabled until principal mapping is implemented."
        )

    if cfg.email_backend == "resend" and not cfg.resend_api_key:
        raise RuntimeError("TREADSTONE_RESEND_API_KEY must be set when TREADSTONE_EMAIL_BACKEND=resend.")

    if not cfg.metering_enforcement_enabled:
        _logger.warning(
            "TREADSTONE_METERING_ENFORCEMENT_ENABLED is False — all quota checks are bypassed. "
            "Set to True before production deployment."
        )

    if cfg.sandbox_domain and not is_local_sandbox_domain(cfg.sandbox_domain):
        parsed = urlparse(cfg.app_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or is_local_hostname(parsed.hostname):
            raise RuntimeError(
                "TREADSTONE_APP_BASE_URL must be set to the public app origin "
                "(e.g. https://app.treadstone-ai.dev) when sandbox Web UI subdomains are enabled."
            )
