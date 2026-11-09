"""Configuration du service Commandes (12-factor)."""

from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "marcheci-commandes"
    environment: str = "development"
    cors_origins: str = ""

    database_url: str = "sqlite:///./commandes_dev.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Entrées externes
    catalogue_url: str = "http://catalogue:8000"
    utilisateurs_url: str = "http://utilisateurs:8000"
    request_timeout_seconds: float = 5.0

    # RabbitMQ (édition des événements de commande)
    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_exchange: str = "marcheci"
    orders_queue: str = "order.created"
    orders_dlq: str = "order.created.dlq"
    consumer_max_retries: int = 3
    consumer_retry_backoff_seconds: float = 2.0
    events_enabled: bool = True

    # JWT (décodage) + compte système pour les appels inter-services (ADMIN)
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "marcheci"
    jwt_audience: str = "marcheci"
    svc_commandes_email: str = "svc.commandes@marcheci.ci"
    svc_commandes_password: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for attr, env_name in (("database_url", "DATABASE_URL_FILE"), ("jwt_secret", "JWT_SECRET_FILE"), ("rabbitmq_password", "RABBITMQ_PASSWORD_FILE"), ("svc_commandes_password", "SVC_COMMANDES_PASSWORD_FILE")):
        secret_path = os.environ.get(env_name)
        if secret_path:
            value = Path(secret_path).read_text(encoding="utf-8").strip()
            if not value:
                raise ValueError(f"Le secret {env_name} est vide")
            setattr(settings, attr, value)
    return settings
