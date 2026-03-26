from fastapi import APIRouter

from treadstone.api.schemas import ConfigResponse
from treadstone.config import settings
from treadstone.core.users import get_github_oauth_client, get_google_oauth_client

router = APIRouter(prefix="/v1", tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def get_config():
    login_methods = ["email"]
    if get_google_oauth_client():
        login_methods.append("google")
    if get_github_oauth_client():
        login_methods.append("github")

    auth_config: dict = {"type": settings.auth_type, "login_methods": login_methods}

    if settings.auth_type == "auth0":
        auth_config["auth0"] = {"domain": settings.auth0_domain, "client_id": settings.auth0_client_id}
    elif settings.auth_type == "authing":
        auth_config["authing"] = {"domain": settings.authing_domain, "app_id": settings.authing_app_id}
    elif settings.auth_type == "logto":
        auth_config["logto"] = {"domain": settings.logto_domain, "app_id": settings.logto_app_id}

    return {"auth": auth_config}
