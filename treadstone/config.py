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

    model_config = {"env_prefix": "TREADSTONE_", "env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
