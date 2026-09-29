import pytest
from pydantic import ValidationError

from app.config import Settings


def _production_settings(**overrides):
    values = {
        "app_env": "production",
        "auth_provider": "wechat",
        "payment_provider": "wechat",
        "refund_provider": "wechat",
        "session_signing_key": "x" * 48,
        "cors_allowed_origins": "https://admin.example.com",
        "expose_api_docs": False,
        "wechat_app_id": "wx-app",
        "wechat_app_secret": "app-secret",
        "wechat_mch_id": "mch-1",
        "wechat_mch_cert_serial": "serial-1",
        "wechat_mch_private_key": "private-key",
        "wechat_notify_url": "https://api.example.com/api/v1/payments/wechat/callback",
        "wechat_refund_notify_url": "https://api.example.com/api/v1/refunds/wechat/callback",
        "wechat_pay_api_v3_key": "0123456789abcdef0123456789abcdef",
        "wechat_pay_platform_cert_serial": "platform-serial",
        "wechat_pay_platform_certificate": "platform-cert",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_config_accepts_explicit_wechat_configuration():
    settings = _production_settings()
    assert settings.is_production is True
    assert settings.cors_origins == ["https://admin.example.com"]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("auth_provider", "mock", "AUTH_PROVIDER_MUST_BE_WECHAT"),
        ("payment_provider", "mock", "PAYMENT_PROVIDER_MUST_BE_WECHAT"),
        ("session_signing_key", "short", "SESSION_SIGNING_KEY_WEAK"),
        (
            "wechat_notify_url",
            "http://localhost/callback",
            "WECHAT_NOTIFY_URL_MUST_BE_PUBLIC_HTTPS",
        ),
        (
            "cors_allowed_origins",
            "http://localhost:5173",
            "CORS_ORIGIN_MUST_BE_PUBLIC_HTTPS",
        ),
    ],
)
def test_production_config_fails_closed(field, value, error):
    with pytest.raises(ValidationError, match=error):
        _production_settings(**{field: value})


def test_secret_file_overrides_environment_value(tmp_path):
    secret = tmp_path / "session-key"
    secret.write_text("s" * 48, encoding="utf-8")
    settings = Settings(
        _env_file=None,
        session_signing_key="ignored",
        session_signing_key_file=str(secret),
    )
    assert settings.session_signing_key == "s" * 48
