"""Configuration du service Utilisateurs (12-factor)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "marcheci-utilisateurs"
    environment: str = "development"
    cors_origins: str = ""

    database_url: str = "sqlite:///./utilisateurs_dev.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    redis_url: str = "redis://redis:6379/1"
    redis_enabled: bool = True

    # Sécurité : secret depuis config sécurisée (CI), jamais dans le code
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "marcheci"
    jwt_audience: str = "marcheci"
    jwt_expires_minutes: int = 60

    # Anti-brute-force : 5 échecs par email, fenêtre de 5 min
    login_max_failures: int = 5
    login_failure_window_seconds: int = 300

    # Compte système (service Commandes) créé par le script d'amorçage
    system_email: str = "svc.commandes@marcheci.ci"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
