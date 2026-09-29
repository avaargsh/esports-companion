import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, PlayerProfile, User


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int
    roles: tuple[str, ...]


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID


class SessionService:
    issuer = "esports-companion"

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def roles_for_user(db: Session, user: User) -> tuple[str, ...]:
        if user.status != "ACTIVE":
            return tuple()

        roles = ["USER"]
        player = db.scalar(
            select(PlayerProfile).where(
                PlayerProfile.user_id == user.id,
                PlayerProfile.verification_status == "APPROVED",
            )
        )
        if player:
            roles.append("PLAYER")
        if user.role in {"PLATFORM", "ADMIN"}:
            roles.append("PLATFORM")
        return tuple(roles)

    @staticmethod
    def create_session(
        db: Session,
        *,
        user: User,
        provider: str,
    ) -> TokenPair:
        SessionService._validate_signing_key()
        now = datetime.now(timezone.utc)
        refresh_token = secrets.token_urlsafe(48)
        session = AuthSession(
            user_id=user.id,
            refresh_token_hash=SessionService._hash_refresh(refresh_token),
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
            provider=provider.upper(),
        )
        db.add(session)
        db.flush()
        roles = SessionService.roles_for_user(db, user)
        access_token = SessionService._encode_access(
            user_id=user.id,
            session_id=session.id,
            roles=roles,
            now=now,
        )
        db.commit()
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=settings.access_token_ttl_seconds,
            refresh_expires_in=settings.refresh_token_ttl_seconds,
            roles=roles,
        )

    @staticmethod
    def rotate_refresh(
        db: Session,
        *,
        refresh_token: str,
    ) -> TokenPair:
        SessionService._validate_signing_key()
        now = datetime.now(timezone.utc)
        token_hash = SessionService._hash_refresh(refresh_token)
        current = db.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == token_hash)
            .with_for_update()
        )
        if not current:
            raise ValueError("REFRESH_TOKEN_INVALID")
        if current.revoked_at is not None:
            raise ValueError("REFRESH_TOKEN_REVOKED")
        if SessionService._as_utc(current.expires_at) <= now:
            raise ValueError("REFRESH_TOKEN_EXPIRED")

        user = db.get(User, current.user_id)
        if not user or user.status != "ACTIVE":
            raise ValueError("USER_INACTIVE")

        current.revoked_at = now
        current.last_used_at = now

        next_refresh = secrets.token_urlsafe(48)
        next_session = AuthSession(
            user_id=user.id,
            refresh_token_hash=SessionService._hash_refresh(next_refresh),
            expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
            rotated_from_id=current.id,
            provider=current.provider,
        )
        db.add(next_session)
        db.flush()

        roles = SessionService.roles_for_user(db, user)
        access_token = SessionService._encode_access(
            user_id=user.id,
            session_id=next_session.id,
            roles=roles,
            now=now,
        )
        db.commit()
        return TokenPair(
            access_token=access_token,
            refresh_token=next_refresh,
            token_type="Bearer",
            expires_in=settings.access_token_ttl_seconds,
            refresh_expires_in=settings.refresh_token_ttl_seconds,
            roles=roles,
        )

    @staticmethod
    def revoke_refresh(
        db: Session,
        *,
        refresh_token: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        token_hash = SessionService._hash_refresh(refresh_token)
        session = db.scalar(
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == token_hash)
            .with_for_update()
        )
        if not session:
            return
        if session.revoked_at is None:
            session.revoked_at = now
        session.last_used_at = now
        db.commit()

    @staticmethod
    def authenticate_access(
        db: Session,
        *,
        access_token: str,
    ) -> tuple[User, AuthSession, tuple[str, ...]]:
        claims = SessionService.decode_access(access_token)
        now = datetime.now(timezone.utc)

        session = db.get(AuthSession, claims.session_id)
        if not session or session.user_id != claims.user_id:
            raise ValueError("ACCESS_SESSION_INVALID")
        if session.revoked_at is not None:
            raise ValueError("ACCESS_SESSION_REVOKED")
        if SessionService._as_utc(session.expires_at) <= now:
            raise ValueError("ACCESS_SESSION_EXPIRED")

        user = db.get(User, claims.user_id)
        if not user or user.status != "ACTIVE":
            raise ValueError("USER_INACTIVE")

        roles = SessionService.roles_for_user(db, user)
        if not roles:
            raise ValueError("USER_INACTIVE")
        return user, session, roles

    @staticmethod
    def decode_access(access_token: str) -> AccessClaims:
        SessionService._validate_signing_key()
        try:
            payload = jwt.decode(
                access_token,
                settings.session_signing_key,
                algorithms=["HS256"],
                issuer=SessionService.issuer,
                options={"require": ["exp", "iat", "sub", "sid", "type"]},
            )
        except jwt.PyJWTError as exc:
            raise ValueError("ACCESS_TOKEN_INVALID") from exc

        if payload.get("type") != "access":
            raise ValueError("ACCESS_TOKEN_INVALID")
        try:
            return AccessClaims(
                user_id=uuid.UUID(str(payload["sub"])),
                session_id=uuid.UUID(str(payload["sid"])),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError("ACCESS_TOKEN_INVALID") from exc

    @staticmethod
    def _encode_access(
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        roles: tuple[str, ...],
        now: datetime,
    ) -> str:
        expires = now + timedelta(seconds=settings.access_token_ttl_seconds)
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "type": "access",
                "roles": list(roles),
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
                "iss": SessionService.issuer,
                "jti": uuid.uuid4().hex,
            },
            settings.session_signing_key,
            algorithm="HS256",
        )

    @staticmethod
    def _hash_refresh(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_signing_key() -> None:
        if settings.is_secure_deployment:
            if (
                settings.session_signing_key == "dev-only-change-me-use-at-least-32-bytes"
                or len(settings.session_signing_key) < 32
            ):
                raise ValueError("PRODUCTION_SESSION_SIGNING_KEY_REQUIRED")
