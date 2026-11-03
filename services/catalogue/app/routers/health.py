"""Healthcheck du service : vérifie la BDD et le cache (optionnel)."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from ..cache import get_product_cache
from ..database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response):
    """200 si la base répond ; 503 sinon. Redis est un composant dégradé (utile au rapport)."""
    ok = True
    components: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        components["database"] = "up"
    except Exception:
        components["database"] = "down"
        ok = False

    cache = get_product_cache()
    components["cache"] = "up" if cache.connected else "degraded"
    # Cache down ≠ service down (mode dégradé assumé), mais documenté avec le service
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ok else "down", "components": components}
