"""Router : consultation des notifications (ADMIN) + healthcheck."""

import logging
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
    """HTTP 200 uniquement si la BDD, RabbitMQ et le consommateur sont prêts."""
    s = get_settings()
    components: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        components["database"] = "up"
    except Exception:
        components["database"] = "down"

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=s.rabbitmq_host,
                port=s.rabbitmq_port,
                credentials=pika.PlainCredentials(s.rabbitmq_user, s.rabbitmq_password),
                socket_timeout=1.5,
                connection_attempts=1,
                heartbeat=0,
            )
        )
        connection.close()
        components["rabbitmq"] = "up"
    except Exception:
        components["rabbitmq"] = "down"

    from ..consumer import get_active_consumer

    consumer = get_active_consumer()
    components["consumer"] = "up" if consumer is not None and consumer.running else "down"
    ready = all(value == "up" for value in components.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ready else "down", "components": components}


@router.post("/internal/replay-dlq")
def replay_dlq(
    _admin: Annotated[dict, Depends(_require_admin)],
    limit: int = Query(default=20, ge=1, le=100),
):
    """Rejoue au plus `limit` messages : publish confirmé avant ack de la DLQ."""
    s = get_settings()
    connection = None
    replayed = 0
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=s.rabbitmq_host,
                port=s.rabbitmq_port,
                credentials=pika.PlainCredentials(s.rabbitmq_user, s.rabbitmq_password),
                socket_timeout=3,
                connection_attempts=1,
                heartbeat=0,
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue=s.orders_dlq, durable=True, passive=True)
        channel.queue_declare(queue=s.orders_queue, durable=True, passive=True)
        channel.confirm_delivery()

        for _ in range(limit):
            method, properties, body = channel.basic_get(queue=s.orders_dlq, auto_ack=False)
            if method is None:
                break
            headers = dict(properties.headers or {})
            headers.pop("x-retry", None)
            headers.pop("reason", None)
            message = pika.BasicProperties(
                content_type=properties.content_type or "application/json",
                delivery_mode=2,
                headers=headers,
            )
            try:
                channel.basic_publish(
                    exchange="",
                    routing_key=s.orders_queue,
                    body=body,
                    properties=message,
                    mandatory=True,
                )
            except (pika.exceptions.UnroutableError, pika.exceptions.NackError):
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                raise
            channel.basic_ack(delivery_tag=method.delivery_tag)
            replayed += 1
        return {"replayed": replayed, "limit": limit}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("event", extra={"event": "dlq_replay_failed"})
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Rejeu DLQ indisponible") from exc
    finally:
        if connection is not None and connection.is_open:
            connection.close()


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
