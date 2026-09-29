import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.providers.registry import get_auth_provider
from app.security import Principal, current_principal, require_session
from app.services.auth_service import AuthService
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class WeChatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refreshToken: str = Field(min_length=20, max_length=512)


class LogoutRequest(BaseModel):
    refreshToken: str = Field(min_length=20, max_length=512)


class LoginResponse(BaseModel):
    userId: str
    provider: str
    isNewUser: bool
    roles: list[str]
    tokenType: str
    accessToken: str
    refreshToken: str
    expiresIn: int
    refreshExpiresIn: int


class RefreshResponse(BaseModel):
    userId: str
    roles: list[str]
    tokenType: str
    accessToken: str
    refreshToken: str
    expiresIn: int
    refreshExpiresIn: int


class MeResponse(BaseModel):
    userId: str
    roles: list[str]
    status: str


class SessionResponse(BaseModel):
    sessionId: str
    provider: str
    current: bool
    createdAt: datetime
    lastUsedAt: datetime | None
    expiresAt: datetime


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
        tokens = SessionService.create_session(
            db,
            user=user,
            provider=provider.name,
        )
        return LoginResponse(
            userId=str(user.id),
            provider=provider.name,
            isNewUser=created,
            roles=list(tokens.roles),
            tokenType=tokens.token_type,
            accessToken=tokens.access_token,
            refreshToken=tokens.refresh_token,
            expiresIn=tokens.expires_in,
            refreshExpiresIn=tokens.refresh_expires_in,
        )
    except ValueError as exc:
        message = str(exc)
        if (
            message.startswith("AUTH_PROVIDER_NOT_CONFIGURED")
            or message.startswith("WECHAT_AUTH_CREDENTIALS_MISSING")
            or message.startswith("PRODUCTION_SESSION_SIGNING_KEY_REQUIRED")
        ):
            raise HTTPException(503, message) from exc
        raise HTTPException(401, message) from exc


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        tokens = SessionService.rotate_refresh(
            db,
            refresh_token=body.refreshToken,
        )
        principal_user = SessionService.decode_access(tokens.access_token).user_id
        return RefreshResponse(
            userId=str(principal_user),
            roles=list(tokens.roles),
            tokenType=tokens.token_type,
            accessToken=tokens.access_token,
            refreshToken=tokens.refresh_token,
            expiresIn=tokens.expires_in,
            refreshExpiresIn=tokens.refresh_expires_in,
        )
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest,
    db: Session = Depends(get_db),
):
    SessionService.revoke_refresh(
        db,
        refresh_token=body.refreshToken,
    )
    return None


@router.get("/sessions", response_model=list[SessionResponse])
def sessions(
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    rows = SessionService.list_active_sessions(
        db,
        user_id=principal.user_id,
    )
    return [
        SessionResponse(
            sessionId=str(row.id),
            provider=row.provider,
            current=row.id == principal.session_id,
            createdAt=row.created_at,
            lastUsedAt=row.last_used_at,
            expiresAt=row.expires_at,
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: uuid.UUID,
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    revoked = SessionService.revoke_user_session(
        db,
        user_id=principal.user_id,
        session_id=session_id,
    )
    if not revoked:
        raise HTTPException(404, "SESSION_NOT_FOUND")
    return None


@router.post("/logout-all", status_code=204)
def logout_all(
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    SessionService.revoke_all_for_user(
        db,
        user_id=principal.user_id,
    )
    return None


@router.get("/me", response_model=MeResponse)
def me(
    principal: Principal = Depends(current_principal),
):
    return MeResponse(
        userId=str(principal.user_id),
        roles=list(principal.roles),
        status=principal.user.status,
    )
