"""Router : consultation des notifications (ADMIN) + healthcheck."""

import logging
import socket
from typing import Annotated

import jwt
import pika
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Base, engine, get_db
from ..models import Notification

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


def _require_admin(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None):
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    s = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            s.jwt_secret,
            algorithms=[s.jwt_algorithm],
            issuer=s.jwt_issuer,
            audience=s.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide") from exc
    if payload.get("role") != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Autorisation administrateur requise")
    return payload


@router.get("/health")
def health(response: Response):
    """BDD + RabbitMQ joignables + thread consommateur vivant."""
    s = get_settings()
    components: dict[str, str] = {}
    core_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        components["database"] = "up"
    except Exception:
        components["database"] = "down"
        core_ok = False

    try:
        with socket.create_connection((s.rabbitmq_host, s.rabbitmq_port), timeout=1.5):
            components["rabbitmq"] = "up"
    except Exception:
        components["rabbitmq"] = "down"

    from ..consumer import get_active_consumer

    consumer = get_active_consumer()
    components["consumer"] = "up" if consumer is not None and consumer.running else "down"

    if not core_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if core_ok else "down", "components": components}


@router.get("/notifications")
def list_notifications(
    _admin: Annotated[dict, Depends(_require_admin)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Historique des notifications (réservé ADMIN)."""
    q = select(Notification).order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = db.scalars(q).all()
    total = db.scalar(select(func.count(Notification.id))) or 0
    return {
        "items": [
            {
                "id": n.id,
                "order_id": n.order_id,
                "user_id": n.user_id,
                "channel": n.channel,
                "recipient": n.recipient,
                "template": n.template,
                "status": n.status,
                "attempts": n.attempts,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
