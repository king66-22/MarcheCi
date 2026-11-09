"""Configuration du service Notifications (12-factor)."""

from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "marcheci-notifications"
    environment: str = "development"
    cors_origins: str = ""

    database_url: str = "sqlite:///./notifications_dev.db"
    db_pool_size: int = 3

    # RabbitMQ — IDENTIQUE au producteur (commandes) pour la topologie
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_exchange: str = "marcheci"
    orders_queue: str = "order.created"
    orders_dlq: str = "order.created.dlq"

    consumer_max_retries: int = 3
    consumer_retry_backoff_seconds: float = 2.0
    consumer_reconnect_seconds: float = 5.0
    events_enabled: bool = True
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "marcheci"
    jwt_audience: str = "marcheci"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for attr, env_name in (("database_url", "DATABASE_URL_FILE"), ("jwt_secret", "JWT_SECRET_FILE"), ("rabbitmq_password", "RABBITMQ_PASSWORD_FILE")):
        secret_path = os.environ.get(env_name)
        if secret_path:
            value = Path(secret_path).read_text(encoding="utf-8").strip()
            if not value:
                raise ValueError(f"Le secret {env_name} est vide")
            setattr(settings, attr, value)
    return settings
