"""Point d'entrée FastAPI du service Catalogue."""

import logging
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .logging_config import setup_logging
from .routers import catalogue, health

setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="MarchéCI — Service Catalogue",
    description="Produits, catégories, stock de la plateforme e-commerce MarchéCI.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Photos produits : en production la gateway sert /media/ depuis le volume
# partagé ; ce montage direct sert au développement local (proxy Vite).
_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=_media_root), name="media")

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def access_log(request: Request, call_next):
    """Log d'accès JSON fondé sur un identifiant d'instance de service (utile à la répartition)."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "event",
        extra={
            "event": "http_access",
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/health", include_in_schema=False)
def root_health():
    from .routers.health import health  # réutilise le check complet
    from fastapi import Response

    response = Response()
    return health(response)


app.include_router(health.router)
app.include_router(catalogue.router)
