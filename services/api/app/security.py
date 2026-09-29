import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.services.session_service import SessionService


@dataclass(frozen=True)
class Principal:
    user: User
    roles: tuple[str, ...]
    session_id: uuid.UUID | None
    legacy: bool = False

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id


def _legacy_headers_allowed() -> bool:
    return not settings.is_secure_deployment


def current_principal(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: uuid.UUID | None = Header(default=None, alias="X-User-Id"),
    x_admin_id: uuid.UUID | None = Header(default=None, alias="X-Admin-Id"),
    db: Session = Depends(get_db),
) -> Principal:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "BEARER_TOKEN_REQUIRED")
        try:
            user, session, roles = SessionService.authenticate_access(
                db,
                access_token=token,
            )
        except ValueError as exc:
            raise HTTPException(401, str(exc)) from exc
        return Principal(
            user=user,
            roles=roles,
            session_id=session.id,
        )

    if _legacy_headers_allowed():
        legacy_id = x_user_id or x_admin_id
        if legacy_id:
            user = db.get(User, legacy_id)
            if not user or user.status != "ACTIVE":
                raise HTTPException(401, "LEGACY_USER_INVALID")
            roles = SessionService.roles_for_user(db, user)
            return Principal(
                user=user,
                roles=roles,
                session_id=None,
                legacy=True,
            )

    raise HTTPException(401, "AUTHENTICATION_REQUIRED")


def current_user_id(
    principal: Principal = Depends(current_principal),
) -> uuid.UUID:
    return principal.user_id


def require_player(
    principal: Principal = Depends(current_principal),
) -> Principal:
    if "PLAYER" not in principal.roles:
        raise HTTPException(403, "PLAYER_REQUIRED")
    return principal


def require_platform(
    principal: Principal = Depends(current_principal),
) -> Principal:
    if "PLATFORM" not in principal.roles:
        raise HTTPException(403, "PLATFORM_REQUIRED")
    return principal
