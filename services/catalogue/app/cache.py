"""Cache Redis de la liste des produits : TTL 60 s + invalidation à l'écriture.

Le cache est optionnel : si Redis est absent, le service continue en mode dégradé.
"""

import logging
from functools import lru_cache
from typing import Any

from redis import Redis

from .config import get_settings

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "products:list"


class ProductCache:
    def __init__(self, url: str, ttl_seconds: int, enabled: bool = True) -> None:
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled
        self._client: Redis | None = None
        if enabled:
            try:
                self._client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
                self._client.ping()
            except Exception as exc:  # pragma: no cover - dépend de l'infra
                logger.warning("Redis indisponible, cache désactivé (%s)", exc)
                self._client = None

    @property
    def connected(self) -> bool:
        """Vérif à la demande (healthcheck)."""
        if self._client is None:
            return False
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def _key(self, query: str, category: str | None, page: int, page_size: int, in_stock: bool) -> str:
        return f"{CACHE_KEY_PREFIX}:{query}|{category or '-'}|{page}|{page_size}|{int(in_stock)}"

    def get_list(self, query: str, category: str | None, page: int, page_size: int, in_stock: bool) -> Any | None:
        if self._client is None:
            return None
        key = self._key(query, category, page, page_size, in_stock)
        try:
            raw = self._client.get(key)
            return raw  # JSON string
        except Exception as exc:
            logger.warning("Lecture cache échouée: %s", exc)
            return None

    def set_list(self, query: str, category: str | None, page: int, page_size: int, in_stock: bool, value: str) -> None:
        if self._client is None:
            return
        key = self._key(query, category, page, page_size, in_stock)
        try:
            self._client.set(key, value, ex=self.ttl_seconds)
        except Exception as exc:
            logger.warning("Écriture cache échouée: %s", exc)

    def invalidate_product_keys(self) -> None:
        """Invalide toutes les clés `products:list:*` (produit créé/modifié/supprimé)."""
        if self._client is None:
            return
        try:
            for key in self._client.scan_iter(f"{CACHE_KEY_PREFIX}:*"):
                self._client.delete(key)
            logger.info("event", extra={"event": "cache_invalidated"})
        except Exception as exc:
            logger.warning("Invalidation cache échouée: %s", exc)


@lru_cache(maxsize=1)
def get_product_cache() -> ProductCache:
    """Client Redis unique par processus (le pool de connexions redis-py est
    thread-safe). Sans ce cache, chaque requête ouvrait une connexion Redis
    et payait un PING de contrôle avant la lecture."""
    settings = get_settings()
    return ProductCache(
        url=settings.redis_url,
        ttl_seconds=settings.products_cache_ttl_seconds,
        enabled=settings.redis_enabled,
    )
