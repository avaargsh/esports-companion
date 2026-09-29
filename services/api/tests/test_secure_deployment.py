from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from app.routers import dev, orders, realtime
from app.security import _legacy_headers_allowed


class FakeWebSocket:
    headers = {}
    query_params = {"user_id": str(uuid4())}


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
