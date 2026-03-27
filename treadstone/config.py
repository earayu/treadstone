from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings

_DEFAULT_JWT_SECRET = "CHANGE_ME_IN_PROD"
_MIN_JWT_SECRET_LENGTH = 32
_UNSUPPORTED_OIDC_AUTH_TYPES = {"auth0", "authing", "logto"}
SANDBOX_STORAGE_SIZE_VALUES = ("5Gi", "10Gi", "20Gi")


class Settings(BaseSettings):
    app_name: str = "treadstone"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/treadstone?sslmode=require"
    # Public API origin used in browser bootstrap redirects and public sandbox Web UI flows.
    api_base_url: str = "http://localhost"

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

    # Sandbox proxy defaults (overridable per-request via X-Sandbox-* headers)
    sandbox_namespace: str = "treadstone-local"
    sandbox_port: int = 8080
    sandbox_proxy_timeout: float = 180.0
    sandbox_storage_class: str = "treadstone-workspace"
    sandbox_default_storage_size: Literal["5Gi", "10Gi", "20Gi"] = "5Gi"

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

    if cfg.sandbox_domain and not is_local_sandbox_domain(cfg.sandbox_domain):
        parsed = urlparse(cfg.api_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or is_local_hostname(parsed.hostname):
            raise RuntimeError(
                "TREADSTONE_API_BASE_URL must be set to the public API origin "
                "when sandbox Web UI subdomains are enabled."
            )
