import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base
from app.main import app
from app.models import AuthSession, PlayerProfile, User
from app.services.session_service import SessionService


def _session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_refresh_rotates_and_revokes_old_access_session():
    Session = _session()
    with Session() as db:
        user = User(openid="session-user", nickname="session-user")
        db.add(user)
        db.commit()
        db.refresh(user)

        first = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )
        rotated = SessionService.rotate_refresh(
            db,
            refresh_token=first.refresh_token,
        )

        with pytest.raises(ValueError, match="ACCESS_SESSION_REVOKED"):
            SessionService.authenticate_access(
                db,
                access_token=first.access_token,
            )

        current_user, current_session, roles = SessionService.authenticate_access(
            db,
            access_token=rotated.access_token,
        )
        assert current_user.id == user.id
        assert current_session.revoked_at is None
        assert roles == ("USER",)

        with pytest.raises(ValueError, match="REFRESH_TOKEN_REUSED"):
            SessionService.rotate_refresh(
                db,
                refresh_token=first.refresh_token,
            )

        with pytest.raises(ValueError, match="ACCESS_SESSION_REVOKED"):
            SessionService.authenticate_access(
                db,
                access_token=rotated.access_token,
            )


def test_logout_with_rotated_refresh_revokes_active_descendants():
    Session = _session()
    with Session() as db:
        user = User(openid="logout-family-user", nickname="logout-family-user")
        db.add(user)
        db.commit()
        db.refresh(user)

        first = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )
        rotated = SessionService.rotate_refresh(
            db,
            refresh_token=first.refresh_token,
        )

        SessionService.revoke_refresh(
            db,
            refresh_token=first.refresh_token,
        )

        with pytest.raises(ValueError, match="ACCESS_SESSION_REVOKED"):
            SessionService.authenticate_access(
                db,
                access_token=rotated.access_token,
            )


def test_list_and_revoke_all_user_sessions():
    Session = _session()
    with Session() as db:
        user = User(openid="multi-session-user", nickname="multi-session-user")
        db.add(user)
        db.commit()
        db.refresh(user)

        first = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )
        second = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )

        active = SessionService.list_active_sessions(
            db,
            user_id=user.id,
        )
        assert len(active) == 2
        assert {row.provider for row in active} == {"MOCK"}

        revoked = SessionService.revoke_all_for_user(
            db,
            user_id=user.id,
        )
        assert revoked == 2
        assert SessionService.list_active_sessions(db, user_id=user.id) == []

        for token in (first.access_token, second.access_token):
            with pytest.raises(ValueError, match="ACCESS_SESSION_REVOKED"):
                SessionService.authenticate_access(
                    db,
                    access_token=token,
                )


def test_roles_are_recomputed_from_current_database_state():
    Session = _session()
    with Session() as db:
        user = User(openid="role-user", nickname="role-user")
        db.add(user)
        db.commit()
        db.refresh(user)

        tokens = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )
        _user, _session_row, roles = SessionService.authenticate_access(
            db,
            access_token=tokens.access_token,
        )
        assert roles == ("USER",)

        db.add(
            PlayerProfile(
                user_id=user.id,
                display_name="role-player",
                verification_status="APPROVED",
                service_status="AVAILABLE",
                rating=Decimal("5.00"),
            )
        )
        db.commit()

        _user, _session_row, roles = SessionService.authenticate_access(
            db,
            access_token=tokens.access_token,
        )
        assert roles == ("USER", "PLAYER")


def test_refresh_tokens_are_stored_only_as_hashes():
    Session = _session()
    with Session() as db:
        user = User(openid="hash-user", nickname="hash-user")
        db.add(user)
        db.commit()
        db.refresh(user)

        tokens = SessionService.create_session(
            db,
            user=user,
            provider="MOCK",
        )
        row = db.scalar(select(AuthSession))
        assert row is not None
        assert row.refresh_token_hash != tokens.refresh_token
        assert len(row.refresh_token_hash) == 64


def test_production_rejects_legacy_identity_header():
    previous = settings.app_env
    settings.app_env = "production"
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/wallet",
                headers={"X-User-Id": str(uuid.uuid4())},
            )
            assert response.status_code == 401
            assert response.json()["detail"] == "AUTHENTICATION_REQUIRED"
    finally:
        settings.app_env = previous

def test_revoke_user_session_is_owner_scoped_and_contains_descendants():
    Session = _session()
    with Session() as db:
        owner = User(openid="session-owner", nickname="session-owner")
        other = User(openid="session-other", nickname="session-other")
        db.add_all([owner, other])
        db.commit()
        db.refresh(owner)
        db.refresh(other)

        first = SessionService.create_session(
            db,
            user=owner,
            provider="MOCK",
        )
        rotated = SessionService.rotate_refresh(
            db,
            refresh_token=first.refresh_token,
        )
        ancestor_id = SessionService.decode_access(first.access_token).session_id

        denied = SessionService.revoke_user_session(
            db,
            user_id=other.id,
            session_id=ancestor_id,
        )
        assert denied is False

        current_user, _current_session, _roles = SessionService.authenticate_access(
            db,
            access_token=rotated.access_token,
        )
        assert current_user.id == owner.id

        revoked = SessionService.revoke_user_session(
            db,
            user_id=owner.id,
            session_id=ancestor_id,
        )
        assert revoked is True

        with pytest.raises(ValueError, match="ACCESS_SESSION_REVOKED"):
            SessionService.authenticate_access(
                db,
                access_token=rotated.access_token,
            )

