from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "dev"
    database_url: str = "postgresql+psycopg://esports:esports@postgres:5432/esports"
    redis_url: str = "redis://redis:6379/0"
    auth_provider: str = "mock"
    payment_provider: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
