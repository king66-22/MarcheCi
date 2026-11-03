"""Client du service Catalogue : vérification serveur des prix et du stock."""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CatalogueProduct:
    id: int
    name: str
    price_xof: int
    stock: int
    is_active: bool


class CatalogueUnavailable(Exception):
    """Le catalogage ne répond pas (crash, réseau, timeout)."""


class CatalogueClient:
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = timeout

    def with_token(self, token: str) -> "CatalogueClient":
        return CatalogueClient(self.base_url, token=token, timeout=self.timeout)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def fetch_products(self, product_ids: list[int]) -> list[CatalogueProduct]:
        """Récupère les produits de référence : NE JAMAIS FAIRE CONFIANCE au prix client."""
        if not product_ids:
            return []
        params = {"ids": ",".join(str(i) for i in sorted(set(product_ids))), "page_size": 200}
        try:
            resp = httpx.get(
                f"{self.base_url}/products",
                params=params,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise CatalogueUnavailable("Catalogue injoignable") from exc

        if resp.status_code != 200:
            raise CatalogueUnavailable(f"Catalogue indisponible ({resp.status_code})")

        try:
            payload = resp.json()
        except ValueError as exc:
            raise CatalogueUnavailable("Réponse catalogue illisible") from exc

        return [
            CatalogueProduct(
                id=p["id"],
                name=p["name"],
                price_xof=int(p["price_xof"]),
                stock=int(p["stock"]),
                is_active=bool(p["is_active"]),
            )
            for p in payload["items"]
        ]

    def adjust_stock(self, product_id: int, delta: int, token: str) -> bool:
        """Décrément/restitue le stock. Lève CatalogueUnavailable si indisponible."""
        try:
            resp = httpx.post(
                f"{self.base_url}/products/{product_id}/adjust-stock",
                json={"delta": delta},
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise CatalogueUnavailable("Catalogue injoignable (stock)") from exc
        if resp.status_code == 200:
            return True
        if resp.status_code == 409:
            return False  # stock insuffisant (409 du catalogue)
        if resp.status_code in (401, 403):
            # Autorisation : jeton système expiré ou compte mal configuré — signal fort
            logger.warning(
                "Authentification/autorisation stock refusée : status=%s", resp.status_code
            )
            raise CatalogueUnavailable(f"Authentification stock refusée ({resp.status_code})")
        raise CatalogueUnavailable(f"Ajustement stock échoué : {resp.status_code}")
