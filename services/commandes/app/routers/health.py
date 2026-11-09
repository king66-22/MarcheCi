"""Healthcheck du service Commandes : BDD + RabbitMQ + Catalogue (dépendances vérifiées)."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

import httpx
import pika

from ..config import get_settings
from ..database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response):
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

    # Catalogue : dépendance pour la création de commande (indisponible => dégradé, pas down)
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{s.catalogue_url}/health")
        components["catalogue"] = "reachable" if r.status_code == 200 else "broken"
    except Exception:
        components["catalogue"] = "unreachable"

    ready = components["database"] == "up" and components["rabbitmq"] == "up" and components["catalogue"] == "reachable"
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ready else "down", "components": components}
