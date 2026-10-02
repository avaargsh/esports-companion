import base64
import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.providers.auth import WeChatWebAuthProvider
from app.providers.registry import get_auth_provider
from app.security import Principal, current_principal, require_session
from app.models import User
from app.services.auth_service import AuthService
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class WeChatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class AdminQrResponse(BaseModel):
    appId: str
    redirectUri: str
    state: str
    authorizeUrl: str


class AdminQrLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    state: str = Field(min_length=16, max_length=512)


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




_ADMIN_QR_STATE_TTL_SECONDS = 600


def _admin_qr_state_signature(nonce: str, issued_at: str) -> str:
    key = settings.session_signing_key.encode("utf-8")
    message = f"admin-wechat-qr:{nonce}:{issued_at}".encode("utf-8")
    digest = hmac.new(key, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _create_admin_qr_state() -> str:
    nonce = secrets.token_urlsafe(18)
    issued_at = str(int(time.time()))
    signature = _admin_qr_state_signature(nonce, issued_at)
    return f"{nonce}.{issued_at}.{signature}"


def _verify_admin_qr_state(state: str) -> None:
    try:
        nonce, issued_at, signature = state.split(".", 2)
        issued = int(issued_at)
    except (TypeError, ValueError):
        raise HTTPException(400, "WECHAT_QR_STATE_INVALID")

    expected = _admin_qr_state_signature(nonce, issued_at)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(400, "WECHAT_QR_STATE_INVALID")
    if int(time.time()) - issued > _ADMIN_QR_STATE_TTL_SECONDS:
        raise HTTPException(400, "WECHAT_QR_STATE_EXPIRED")


def get_wechat_web_auth_provider() -> WeChatWebAuthProvider:
    return WeChatWebAuthProvider(
        app_id=settings.wechat_web_app_id,
        app_secret=settings.wechat_web_app_secret,
        redirect_uri=settings.wechat_web_redirect_uri,
    )


def _issue_platform_session(
    db: Session,
    *,
    user: User,
    provider: str,
    provider_session_key: str | None,
    is_new_user: bool = False,
) -> LoginResponse:
    roles = SessionService.roles_for_user(db, user)
    if "PLATFORM" not in roles:
        raise HTTPException(403, "PLATFORM_REQUIRED")
    tokens = SessionService.create_session(
        db,
        user=user,
        provider=provider,
        provider_session_key=provider_session_key,
    )
    return LoginResponse(
        userId=str(user.id),
        provider=provider,
        isNewUser=is_new_user,
        roles=list(tokens.roles),
        tokenType=tokens.token_type,
        accessToken=tokens.access_token,
        refreshToken=tokens.refresh_token,
        expiresIn=tokens.expires_in,
        refreshExpiresIn=tokens.refresh_expires_in,
    )


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
        identity = provider.exchange_code(body.code)
        user, created = AuthService.login_with_identity(
            db,
            identity=identity,
        )
        tokens = SessionService.create_session(
            db,
            user=user,
            provider=provider.name,
            provider_session_key=identity.provider_session_key,
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


@router.post("/wechat/admin-login", response_model=LoginResponse)
def wechat_admin_login(
    body: WeChatLoginRequest,
    db: Session = Depends(get_db),
):
    try:
        provider = get_auth_provider(settings.auth_provider)
        identity = provider.exchange_code(body.code)
        user, created = AuthService.login_with_identity(
            db,
            identity=identity,
        )
        return _issue_platform_session(
            db,
            user=user,
            provider=provider.name,
            provider_session_key=identity.provider_session_key,
            is_new_user=created,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        message = str(exc)
        if (
            message.startswith("AUTH_PROVIDER_NOT_CONFIGURED")
            or message.startswith("WECHAT_AUTH_CREDENTIALS_MISSING")
            or message.startswith("PRODUCTION_SESSION_SIGNING_KEY_REQUIRED")
        ):
            raise HTTPException(503, message) from exc
        raise HTTPException(401, message) from exc


@router.get("/wechat/admin-qr", response_model=AdminQrResponse)
def wechat_admin_qr():
    try:
        provider = get_wechat_web_auth_provider()
        state = _create_admin_qr_state()
        return AdminQrResponse(
            appId=provider.app_id,
            redirectUri=provider.redirect_uri,
            state=state,
            authorizeUrl=provider.authorize_url(state),
        )
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/wechat/admin-qr-login", response_model=LoginResponse)
def wechat_admin_qr_login(
    body: AdminQrLoginRequest,
    db: Session = Depends(get_db),
):
    _verify_admin_qr_state(body.state)
    try:
        provider = get_wechat_web_auth_provider()
        identity = provider.exchange_code(body.code)
    except ValueError as exc:
        message = str(exc)
        status_code = 503 if message == "WECHAT_WEB_AUTH_CREDENTIALS_MISSING" else 401
        raise HTTPException(status_code, message) from exc

    if not identity.union_id:
        raise HTTPException(401, "WECHAT_UNIONID_REQUIRED")

    user = db.scalar(select(User).where(User.unionid == identity.union_id))
    if not user or user.status != "ACTIVE":
        raise HTTPException(403, "PLATFORM_REQUIRED")

    return _issue_platform_session(
        db,
        user=user,
        provider=provider.name,
        provider_session_key=identity.provider_session_key,
    )


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
