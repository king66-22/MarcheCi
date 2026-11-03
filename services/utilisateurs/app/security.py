"""Sécurité : hachage Argon2id, création/validation JWT, anti-brute-force Redis."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from redis import Redis
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import User

logger = logging.getLogger(__name__)

# Argon2id — jamais de mot de passe en clair en base
_ph = PasswordHasher()

_bearer = HTTPBearer(auto_error=False)


class RateLimiter:
    """Compteur d'échecs de connexion par email (fenêtre glissante Redis)."""

    def __init__(self, url: str, max_failures: int, window: int, enabled: bool = True):
        self.max_failures = max_failures
        self.window = window
        self.enabled = enabled
        self._redis: Redis | None = None
        if enabled:
            try:
                self._redis = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
                self._redis.ping()
            except Exception as exc:
                logger.warning("Redis absent : rate-limit login désactivé (%s)", exc)
                self._redis = None

    def is_blocked(self, key: str) -> bool:
        if self._redis is None:
            return False
        count = self._redis.get(f"loginfail:{key.lower()}") or "0"
        return int(count) >= self.max_failures

    def register_failure(self, key: str) -> None:
        if self._redis is None:
            return
        r_key = f"loginfail:{key.lower()}"
        try:
            new = self._redis.incr(r_key)
            if new == 1:
                self._redis.expire(r_key, self.window)
        except Exception as exc:
            logger.warning("Échec enregistrement rate-limit (%s)", exc)

    def reset(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            self._redis.delete(f"loginfail:{key.lower()}")
        except Exception:
            pass


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        s = get_settings()
        _rate_limiter = RateLimiter(s.redis_url, s.login_max_failures, s.login_failure_window_seconds, s.redis_enabled)
    return _rate_limiter


def set_rate_limiter_for_tests(rl: RateLimiter) -> None:
    global _rate_limiter
    _rate_limiter = rl


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user: User) -> tuple[str, int]:
    s = get_settings()
    expires_in = s.jwt_expires_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, expires_in


def decode_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            issuer=s.jwt_issuer,
            audience=s.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée, reconnectez-vous") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide") from exc


def get_current_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    return decode_token(credentials.credentials)


def get_current_user(
    payload: Annotated[dict, Depends(get_current_payload)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte introuvable")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorisation administrateur requise")
    return user
