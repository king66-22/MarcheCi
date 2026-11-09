"""Dépendances d'authentification et d'autorisation (JWT émis par le service Utilisateurs)."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db

_bearer = HTTPBearer(auto_error=False)


def decode_token(token: str) -> dict:
    """Décode + valide un JWT avec le secret partagé (config sécurisée)."""
    plugin = get_settings()
    try:
        payload = jwt.decode(
            token,
            plugin.jwt_secret,
            algorithms=[plugin.jwt_algorithm],
            issuer=plugin.jwt_issuer,
            audience=plugin.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton expiré") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide") from exc
    return payload


def get_current_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    return decode_token(credentials.credentials)


def require_admin(payload: Annotated[dict, Depends(get_current_payload)]) -> dict:
    role = payload.get("role")
    if role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorisation administrateur requise")
    return payload


def require_merchant_or_admin(payload: Annotated[dict, Depends(get_current_payload)]) -> dict:
    """Gestion du catalogue : commerçant propriétaire ou administrateur."""
    role = payload.get("role")
    if role not in ("COMMERCANT", "ADMIN"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Espace commerçant requis (rôle COMMERCANT) ou autorisation administrateur",
        )
    return payload


def assert_can_manage_product(payload: dict, product) -> None:
    """Un commerçant ne peut gérer que ses propres produits ; un ADMIN gère tout."""
    if payload.get("role") == "ADMIN":
        return
    try:
        owner_id = int(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide") from exc
    if payload.get("role") == "COMMERCANT" and product.owner_id == owner_id:
        return
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "Vous ne pouvez gérer que les produits de votre boutique",
    )


# Jalon : réutilisation pour vérifier le rôle du compte système qui appelle les opérations
# internes (décrément stock par le service Commandes). Le compte système a un rôle ADMIN.
AdminPayloadDep = Annotated[dict, Depends(require_admin)]
MerchantPayloadDep = Annotated[dict, Depends(require_merchant_or_admin)]
DBDep = Annotated[Session, Depends(get_db)]
