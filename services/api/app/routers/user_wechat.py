import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.providers.object_storage import MinIOImageStorage
from app.providers.wechat_user import (
    WeChatMiniProgramClient,
    WeChatSession,
    decrypt_phone_number,
)
from app.security import Principal, require_session
from app.services.session_service import SessionService
from app.status_labels import COMMON_STATUS_TEXT, status_text


router = APIRouter(prefix="/api/user", tags=["wechat-user"])


class WxLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class BindPhoneRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=256)
    encryptedData: str | None = Field(default=None, min_length=1)
    iv: str | None = Field(default=None, min_length=1)


class UserProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatarUrl: str | None = Field(default=None, max_length=512)


class UserAvatarUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    contentType: str = Field(default="application/octet-stream", max_length=128)
    dataBase64: str = Field(min_length=1)


class StandardResponse(BaseModel):
    code: int
    message: str
    data: Any = None


def get_wechat_client() -> WeChatMiniProgramClient:
    return WeChatMiniProgramClient(
        app_id=settings.wechat_app_id,
        app_secret=settings.wechat_app_secret,
    )


def ok(data: Any) -> StandardResponse:
    return StandardResponse(code=0, message="ok", data=data)


def _storage() -> MinIOImageStorage:
    return MinIOImageStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket_name=settings.minio_bucket_name,
        secure=settings.minio_secure,
        public_url=settings.minio_public_url,
    )


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "userId": str(user.id),
        "openid": user.openid,
        "nickname": user.nickname or "微信用户",
        "avatarUrl": user.avatar_url,
        "phone": user.phone,
        "role": user.role,
        "status": status_text(user.status, COMMON_STATUS_TEXT),
        "statusCode": user.status,
    }


def fail(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": 1, "message": message, "data": None},
    )


def _get_or_create_user(db: Session, session: WeChatSession) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.openid == session.openid))
    if user:
        changed = False
        if session.unionid and user.unionid != session.unionid:
            user.unionid = session.unionid
            changed = True
        if changed:
            db.commit()
            db.refresh(user)
        return user, False

    user = User(
        openid=session.openid,
        unionid=session.unionid,
        nickname="微信用户",
        role="USER",
        status="ACTIVE",
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user, True
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(User).where(User.openid == session.openid))
        if not existing:
            raise
        return existing, False


@router.post("/wx-login", response_model=StandardResponse)
def wx_login(
    body: WxLoginRequest,
    db: Session = Depends(get_db),
    client: WeChatMiniProgramClient = Depends(get_wechat_client),
):
    try:
        wechat_session = client.code2session(body.code)
        user, created = _get_or_create_user(db, wechat_session)
        tokens = SessionService.create_session(
            db,
            user=user,
            provider="WECHAT",
            provider_session_key=wechat_session.session_key,
        )
        return ok(
            {
                "userId": str(user.id),
                "openid": user.openid,
                "isNewUser": created,
                "tokenType": tokens.token_type,
                "token": tokens.access_token,
                "accessToken": tokens.access_token,
                "refreshToken": tokens.refresh_token,
                "expiresIn": tokens.expires_in,
                "refreshExpiresIn": tokens.refresh_expires_in,
                "roles": list(tokens.roles),
                "nickname": user.nickname or "微信用户",
                "avatarUrl": user.avatar_url,
                "phone": user.phone,
            }
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 503 if message == "WECHAT_AUTH_CREDENTIALS_MISSING" else 400
        return fail(status_code, message)
    except Exception:
        return fail(500, "WECHAT_LOGIN_FAILED")


@router.post("/bind-phone", response_model=StandardResponse)
def bind_phone(
    body: BindPhoneRequest,
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    try:
        if body.code:
            payload = get_wechat_client().get_phone_number(body.code)
        else:
            from app.models import AuthSession

            auth_session = db.get(AuthSession, principal.session_id)
            if not body.encryptedData or not body.iv:
                return fail(400, "WECHAT_PHONE_CREDENTIALS_MISSING")
            if not auth_session or not auth_session.provider_session_key:
                return fail(400, "WECHAT_SESSION_KEY_MISSING")
            payload = decrypt_phone_number(
                encrypted_data=body.encryptedData,
                iv=body.iv,
                session_key=auth_session.provider_session_key,
                expected_app_id=settings.wechat_app_id,
            )
        phone = str(payload.get("purePhoneNumber") or payload.get("phoneNumber"))
        user = db.get(User, principal.user_id)
        if not user:
            return fail(401, "USER_NOT_FOUND")
        user.phone = phone
        db.commit()
        return ok({"phone": phone, "bound": True})
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception:
        return fail(500, "WECHAT_PHONE_BIND_FAILED")


@router.get("/me", response_model=StandardResponse)
def get_current_user_profile(
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    user = db.get(User, principal.user_id)
    if not user:
        return fail(401, "USER_NOT_FOUND")
    return ok(_user_payload(user))


@router.post("/profile", response_model=StandardResponse)
@router.patch("/profile", response_model=StandardResponse)
def update_current_user_profile(
    body: UserProfileUpdateRequest,
    principal: Principal = Depends(require_session),
    db: Session = Depends(get_db),
):
    user = db.get(User, principal.user_id)
    if not user:
        return fail(401, "USER_NOT_FOUND")
    if body.nickname is not None:
        user.nickname = body.nickname.strip()
    if body.avatarUrl is not None:
        user.avatar_url = body.avatarUrl.strip() or None
    db.commit()
    db.refresh(user)
    return ok(_user_payload(user))


@router.post("/avatar", status_code=201, response_model=StandardResponse)
def upload_current_user_avatar(
    body: UserAvatarUploadRequest,
    principal: Principal = Depends(require_session),
):
    try:
        content = base64.b64decode(body.dataBase64, validate=True)
    except (binascii.Error, ValueError):
        return fail(400, "INVALID_IMAGE_DATA")
    if not content:
        return fail(400, "EMPTY_IMAGE")
    if len(content) > 5 * 1024 * 1024:
        return fail(413, "IMAGE_TOO_LARGE")
    try:
        storage = _storage()
        key = storage.upload_image_bytes(
            filename=body.filename,
            content=content,
            content_type=body.contentType,
        )
        return ok({"key": key, "url": storage.get_public_url(key)})
    except ValueError as exc:
        return fail(400, str(exc))
    except Exception:
        return fail(500, "USER_AVATAR_UPLOAD_FAILED")
