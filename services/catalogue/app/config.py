"""Configuration du service Catalogue (12-factor : tout vient de l'environnement)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "marcheci-catalogue"
    environment: str = "development"
    # CORS strict : liste d'origines autorisées, vide = same-origin via gateway
    cors_origins: str = ""

    # Base de données (défaut local dev ; en prod : PostgreSQL via compose)
    database_url: str = "sqlite:///./catalogue_dev.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://redis:6379/0"
    redis_enabled: bool = True
    products_cache_ttl_seconds: int = 60  # exigence : 60 secondes

    # Authentification (jeton émis par le service Utilisateurs, secret partagé)
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "marcheci"
    jwt_audience: str = "marcheci"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
