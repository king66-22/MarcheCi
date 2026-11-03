"""Healthcheck du service utilisateurs."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "components": {"database": "up"}}
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "down", "components": {"database": "down"}}
