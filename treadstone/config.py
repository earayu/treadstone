from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "treadstone"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/treadstone?sslmode=require"

    # Auth
    auth_type: str = "cookie"  # cookie | auth0 | authing | logto | none
    register_mode: str = "unlimited"  # unlimited | invitation
    jwt_secret: str = "CHANGE_ME_IN_PROD"
    oauth_redirect_url: str = "http://localhost:3000/auth/callback"

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

    # Leader election for singleton background sync tasks in multi-replica deploys
    leader_election_enabled: bool = False
    leader_election_lease_name: str = "treadstone-sync-leader"
    leader_election_lease_duration_seconds: int = 15
    leader_election_renew_interval_seconds: int = 5
    leader_election_retry_interval_seconds: int = 2
    pod_name: str = ""
    pod_namespace: str = ""

    # Subdomain-based sandbox routing (for browser Web UI access)
    # Dev: "sandbox.localhost"  →  sandbox-{name}.sandbox.localhost[:port]
    # Prod: "treadstone-ai.dev" →  sandbox-{name}.treadstone-ai.dev
    # Empty string disables subdomain routing.
    sandbox_domain: str = ""

    # Only subdomains starting with this prefix are treated as sandbox Web UI
    # traffic.  Non-matching subdomains (api, www, docs, …) pass through to
    # the normal FastAPI app.  Override via TREADSTONE_SANDBOX_SUBDOMAIN_PREFIX.
    sandbox_subdomain_prefix: str = "sandbox-"

    model_config = {"env_prefix": "TREADSTONE_", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
