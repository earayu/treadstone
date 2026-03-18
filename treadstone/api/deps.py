from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from treadstone.auth import tv
from treadstone.config import settings
from treadstone.core.database import get_session
from treadstone.core.users import fastapi_users
from treadstone.models.api_key import ApiKey
from treadstone.models.user import Role, User

bearer_scheme = HTTPBearer(auto_error=False)

optional_current_user = fastapi_users.current_user(optional=True, active=True)
required_current_user = fastapi_users.current_user(active=True)


async def authenticate_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Bearer sk-xxx -> API Key auth"""
    if not credentials or not credentials.credentials.startswith("sk-"):
        return None
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key == credentials.credentials,
            ApiKey.gmt_deleted.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        return None
    user_result = await session.execute(select(User).where(User.id == api_key.user_id))
    return user_result.scalar_one_or_none()


async def authenticate_oidc_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    """Bearer <jwt> -> external OIDC verification (auth0 / authing / logto)"""
    if settings.auth_type not in ("auth0", "authing", "logto"):
        return None
    if not credentials or credentials.credentials.startswith("sk-"):
        return None
    if tv is None:
        return None
    try:
        tv.verify(credentials.credentials)
        return None
    except Exception:
        return None


async def get_current_user(
    request: Request,
    api_key_user: User | None = Depends(authenticate_api_key),
    cookie_user: User | None = Depends(optional_current_user),
) -> User:
    """Priority: API Key -> Cookie/JWT Session"""
    user = api_key_user or cookie_user
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user
