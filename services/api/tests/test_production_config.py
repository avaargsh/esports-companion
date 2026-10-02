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
        "minio_public_url": "https://api.example.com",
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
        (
            "minio_public_url",
            "http://localhost:9000",
            "MINIO_PUBLIC_URL_MUST_BE_PUBLIC_HTTPS",
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



def test_staging_is_a_secure_wechat_deployment():
    settings = _production_settings(app_env="staging")
    assert settings.is_production is False
    assert settings.is_secure_deployment is True


def test_staging_rejects_mock_providers():
    with pytest.raises(
        ValidationError,
        match="STAGING_CONFIG_INVALID:AUTH_PROVIDER_MUST_BE_WECHAT",
    ):
        _production_settings(app_env="staging", auth_provider="mock")


def test_minio_secret_files_override_environment_values(tmp_path):
    access_key = tmp_path / "minio_access_key"
    secret_key = tmp_path / "minio_secret_key"
    access_key.write_text("prod-minio-access", encoding="utf-8")
    secret_key.write_text("prod-minio-secret", encoding="utf-8")

    settings = Settings(
        _env_file=None,
        minio_access_key="ignored",
        minio_secret_key="ignored",
        minio_access_key_file=str(access_key),
        minio_secret_key_file=str(secret_key),
    )

    assert settings.minio_access_key == "prod-minio-access"
    assert settings.minio_secret_key == "prod-minio-secret"
