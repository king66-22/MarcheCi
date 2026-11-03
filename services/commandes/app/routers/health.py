"""Healthcheck du service Commandes : BDD + RabbitMQ + Catalogue (dépendances vérifiées)."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

import httpx

from ..config import get_settings
from ..database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response):
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

    # RabbitMQ : socket de test (option, best effort)
    import socket

    try:
        with socket.create_connection((s.rabbitmq_host, s.rabbitmq_port), timeout=1.5):
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

    if not core_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if core_ok else "down", "components": components}
