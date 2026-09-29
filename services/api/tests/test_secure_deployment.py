from app.config import settings
from app.routers import dev, orders, realtime
from app.security import _legacy_headers_allowed


def test_staging_disables_demo_and_legacy_identity(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")

    assert settings.is_secure_deployment is True
    assert _legacy_headers_allowed() is False

    try:
        dev._ensure_demo_mode()
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404
    else:
        raise AssertionError("staging demo mode must be disabled")


def test_staging_websocket_query_identity_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "staging")
    assert settings.is_secure_deployment is True
    assert realtime.settings.is_secure_deployment is True
    assert orders.settings.is_secure_deployment is True
