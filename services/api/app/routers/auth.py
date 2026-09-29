from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.providers.registry import get_auth_provider
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class WeChatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    userId: str
    provider: str
    isNewUser: bool


@router.post("/wechat/login", response_model=LoginResponse)
def wechat_login(
    body: WeChatLoginRequest,
    db: Session = Depends(get_db),
):
    try:
        provider = get_auth_provider(settings.auth_provider)
        user, created = AuthService.login_with_code(
            db,
            provider=provider,
            code=body.code,
        )
        return LoginResponse(
            userId=str(user.id),
            provider=provider.name,
            isNewUser=created,
        )
    except ValueError as exc:
        message = str(exc)
        if message.startswith("AUTH_PROVIDER_NOT_CONFIGURED"):
            raise HTTPException(503, message) from exc
        raise HTTPException(401, message) from exc
