from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://esports:esports@postgres:5432/esports"
    redis_url: str = "redis://redis:6379/0"
    auth_provider: str = "mock"
    payment_provider: str = "mock"

    session_signing_key: str = "dev-only-change-me"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2592000

    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_mch_id: str = ""
    wechat_mch_cert_serial: str = ""
    wechat_mch_private_key: str = ""
    wechat_notify_url: str = ""
    wechat_pay_api_base_url: str = "https://api.mch.weixin.qq.com"
    wechat_pay_api_v3_key: str = ""
    wechat_pay_platform_cert_serial: str = ""
    wechat_pay_platform_certificate: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
