from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from app.models import User
from app.routers import dev, orders, realtime
from app.security import (
    Principal,
    _legacy_headers_allowed,
    require_platform,
    require_player,
    require_session,
)


class FakeWebSocket:
    headers = {}
    query_params = {"user_id": str(uuid4())}


def _principal(*roles: str, legacy: bool = False) -> Principal:
    return Principal(
        user=User(id=uuid4(), nickname="security-test"),
        roles=roles,
        session_id=None if legacy else uuid4(),
        legacy=legacy,
    )


def test_staging_disables_demo_and_legacy_identity(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")

    assert settings.is_secure_deployment is True
    assert _legacy_headers_allowed() is False

    with pytest.raises(HTTPException) as exc:
        dev._ensure_demo_mode()
    assert exc.value.status_code == 404


def test_staging_disables_mock_payment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")

    with pytest.raises(HTTPException) as exc:
        orders.mock_pay(
            order_id=uuid4(),
            idempotency_key="staging-mock-pay",
            user_id=uuid4(),
            db=None,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "MOCK_PAYMENT_DISABLED"


def test_staging_websocket_query_identity_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")

    identity = realtime._authenticate_websocket(
        FakeWebSocket(),
        db=None,
    )
    assert identity is None


def test_session_management_rejects_legacy_principal():
    with pytest.raises(HTTPException) as exc:
        require_session(_principal("USER", legacy=True))

    assert exc.value.status_code == 401
    assert exc.value.detail == "SESSION_AUTH_REQUIRED"


@pytest.mark.parametrize(
    ("guard", "role"),
    [
        (require_player, "PLAYER"),
        (require_platform, "PLATFORM"),
    ],
)
def test_privileged_role_guards_reject_legacy_identity(guard, role):
    with pytest.raises(HTTPException) as exc:
        guard(_principal("USER", role, legacy=True))

    assert exc.value.status_code == 401
    assert exc.value.detail == "SESSION_AUTH_REQUIRED"


@pytest.mark.parametrize(
    ("guard", "role"),
    [
        (require_player, "PLAYER"),
        (require_platform, "PLATFORM"),
    ],
)
def test_privileged_role_guards_accept_bearer_session(guard, role):
    principal = _principal("USER", role)

    assert guard(principal) is principal


def test_privileged_guards_preserve_role_denial_before_session_check():
    with pytest.raises(HTTPException) as exc:
        require_platform(_principal("USER", legacy=True))

    assert exc.value.status_code == 403
    assert exc.value.detail == "PLATFORM_REQUIRED"
