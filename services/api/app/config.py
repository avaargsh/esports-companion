from pathlib import Path
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PRODUCTION_ENVS = {"prod", "production"}
_SECURE_DEPLOYMENT_ENVS = {"staging", *_PRODUCTION_ENVS}
_DEV_SIGNING_KEY = "dev-only-change-me-use-at-least-32-bytes"


class Settings(BaseSettings):
    app_env: str = "dev"
    service_name: str = "esports-companion-api"
    commit_sha: str = "dev"
    log_level: str = "INFO"
    expose_api_docs: bool = True
    cors_allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173"
    )
    readiness_require_redis: bool = True
    otel_enabled: bool = False
    otel_exporter_otlp_traces_endpoint: str = ""
    otel_trace_sample_ratio: float = 0.10
    otel_export_timeout_seconds: float = 5.0

    database_url: str = "postgresql+psycopg://esports:esports@postgres:5432/esports"
    database_url_file: str = ""
    redis_url: str = "redis://redis:6379/0"
    redis_url_file: str = ""
    auth_provider: str = "mock"
    payment_provider: str = "mock"
    refund_provider: str = "manual"

    session_signing_key: str = _DEV_SIGNING_KEY
    session_signing_key_file: str = ""
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2592000

    finish_confirm_timeout_seconds: int = 1800
    assignment_start_timeout_seconds: int = 600
    order_timeout_scan_seconds: int = 30
    order_timeout_batch_size: int = 50
    refund_reconcile_scan_seconds: int = 60
    refund_reconcile_min_age_seconds: int = 30
    refund_reconcile_batch_size: int = 20
    operational_metrics_scan_seconds: int = 15

    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_app_secret_file: str = ""
    wechat_mch_id: str = ""
    wechat_mch_cert_serial: str = ""
    wechat_mch_private_key: str = ""
    wechat_mch_private_key_file: str = ""
    wechat_notify_url: str = ""
    wechat_refund_notify_url: str = ""
    wechat_pay_api_base_url: str = "https://api.mch.weixin.qq.com"
    wechat_pay_api_v3_key: str = ""
    wechat_pay_api_v3_key_file: str = ""
    wechat_pay_platform_cert_serial: str = ""
    wechat_pay_platform_certificate: str = ""
    wechat_pay_platform_certificate_file: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in _PRODUCTION_ENVS

    @property
    def is_secure_deployment(self) -> bool:
        return self.app_env.strip().lower() in _SECURE_DEPLOYMENT_ENVS

    @property
    def cors_origins(self) -> list[str]:
        return [
            item.strip()
            for item in self.cors_allowed_origins.split(",")
            if item.strip()
        ]

    @model_validator(mode="after")
    def resolve_secrets_and_validate(self):
        self._load_secret_file("database_url", "database_url_file")
        self._load_secret_file("redis_url", "redis_url_file")
        self._load_secret_file("session_signing_key", "session_signing_key_file")
        self._load_secret_file("wechat_app_secret", "wechat_app_secret_file")
        self._load_secret_file(
            "wechat_mch_private_key",
            "wechat_mch_private_key_file",
        )
        self._load_secret_file(
            "wechat_pay_api_v3_key",
            "wechat_pay_api_v3_key_file",
        )
        self._load_secret_file(
            "wechat_pay_platform_certificate",
            "wechat_pay_platform_certificate_file",
        )

        if self.access_token_ttl_seconds <= 0:
            raise ValueError("ACCESS_TOKEN_TTL_MUST_BE_POSITIVE")
        if self.refresh_token_ttl_seconds <= self.access_token_ttl_seconds:
            raise ValueError("REFRESH_TOKEN_TTL_MUST_EXCEED_ACCESS_TOKEN_TTL")
        if not 0.0 <= self.otel_trace_sample_ratio <= 1.0:
            raise ValueError("OTEL_TRACE_SAMPLE_RATIO_OUT_OF_RANGE")
        if self.otel_export_timeout_seconds <= 0:
            raise ValueError("OTEL_EXPORT_TIMEOUT_MUST_BE_POSITIVE")
        if self.otel_enabled:
            parsed_otel = urlparse(self.otel_exporter_otlp_traces_endpoint)
            if (
                parsed_otel.scheme not in {"http", "https"}
                or not parsed_otel.netloc
            ):
                raise ValueError("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT_INVALID")

        if self.is_secure_deployment:
            self._validate_secure_deployment()
        return self

    def _load_secret_file(self, value_field: str, file_field: str) -> None:
        file_path = getattr(self, file_field).strip()
        if not file_path:
            return
        path = Path(file_path)
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError(
                f"SECRET_FILE_UNREADABLE:{file_field}:{file_path}"
            ) from exc
        if not value:
            raise ValueError(f"SECRET_FILE_EMPTY:{file_field}:{file_path}")
        setattr(self, value_field, value)

    def _validate_secure_deployment(self) -> None:
        errors: list[str] = []

        if self.auth_provider.strip().lower() != "wechat":
            errors.append("AUTH_PROVIDER_MUST_BE_WECHAT")
        if self.payment_provider.strip().lower() != "wechat":
            errors.append("PAYMENT_PROVIDER_MUST_BE_WECHAT")
        if self.refund_provider.strip().lower() not in {"wechat", "manual"}:
            errors.append("REFUND_PROVIDER_INVALID")

        if (
            self.session_signing_key == _DEV_SIGNING_KEY
            or len(self.session_signing_key) < 32
        ):
            errors.append("SESSION_SIGNING_KEY_WEAK")

        required = {
            "WECHAT_APP_ID": self.wechat_app_id,
            "WECHAT_APP_SECRET": self.wechat_app_secret,
            "WECHAT_MCH_ID": self.wechat_mch_id,
            "WECHAT_MCH_CERT_SERIAL": self.wechat_mch_cert_serial,
            "WECHAT_MCH_PRIVATE_KEY": self.wechat_mch_private_key,
            "WECHAT_NOTIFY_URL": self.wechat_notify_url,
            "WECHAT_PAY_API_V3_KEY": self.wechat_pay_api_v3_key,
            "WECHAT_PAY_PLATFORM_CERT_SERIAL": self.wechat_pay_platform_cert_serial,
            "WECHAT_PAY_PLATFORM_CERTIFICATE": self.wechat_pay_platform_certificate,
        }
        if self.refund_provider.strip().lower() == "wechat":
            required["WECHAT_REFUND_NOTIFY_URL"] = self.wechat_refund_notify_url
        for name, value in required.items():
            if not value:
                errors.append(f"{name}_REQUIRED")

        for name, value in {
            "WECHAT_NOTIFY_URL": self.wechat_notify_url,
            "WECHAT_REFUND_NOTIFY_URL": self.wechat_refund_notify_url,
        }.items():
            if value and not self._is_public_https(value):
                errors.append(f"{name}_MUST_BE_PUBLIC_HTTPS")

        if not self.cors_origins:
            errors.append("CORS_ALLOWED_ORIGINS_REQUIRED")
        for origin in self.cors_origins:
            parsed = urlparse(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or parsed.hostname in {"localhost", "127.0.0.1"}
            ):
                errors.append("CORS_ORIGIN_MUST_BE_PUBLIC_HTTPS")
                break

        if errors:
            prefix = (
                "PRODUCTION_CONFIG_INVALID"
                if self.is_production
                else "STAGING_CONFIG_INVALID"
            )
            raise ValueError(prefix + ":" + ",".join(errors))

    @staticmethod
    def _is_public_https(value: str) -> bool:
        parsed = urlparse(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and parsed.hostname not in {"localhost", "127.0.0.1"}
        )


settings = Settings()
