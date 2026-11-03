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


# Jalon : réutilisation pour vérifier le rôle du compte système qui appelle les opérations
# internes (décrément stock par le service Commandes). Le compte système a un rôle ADMIN.
AdminPayloadDep = Annotated[dict, Depends(require_admin)]
DBDep = Annotated[Session, Depends(get_db)]
