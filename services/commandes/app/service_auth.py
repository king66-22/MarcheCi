"""Authentification du service Commandes auprès du service Utilisateurs.

Le décrément de stock côté Catalogue exige le rôle ADMIN. Un compte système
`svc.commandes` (créé par le script d'amorçage du déploiement) est utilisé :
login → JWT retiré au premier appel, mis en cache jusqu'à expiration.
"""

import logging
import time
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


class ServiceAuth:
    """Gestion simplifiée du jeton du compte système (cache + rafraîchissement)."""

    def __init__(self, users_url: str, email: str, password: str):
        self.users_url = users_url.rstrip("/")
        self.email = email
        self.password = password
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 30:
            return self._token
        if not self.password:
            logger.warning("Compte système non configuré (svc_commandes_password vide)")
            raise RuntimeError("Compte système Commandes non configuré")
        try:
            resp = httpx.post(
                f"{self.users_url}/auth/login",
                json={"email": self.email, "password": self.password},
                timeout=5.0,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.error("Impossible d'obtenir un jeton système : %s", exc)
            raise RuntimeError("Service utilisateurs injoignable pour l'auth système") from exc
        self._token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token
