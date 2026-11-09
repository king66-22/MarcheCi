"""Point d'entrée FastAPI du service Commandes."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .logging_config import setup_logging
from .routers import health, orders
from .outbox import OutboxWorker

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()
outbox_worker = OutboxWorker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.events_enabled:
        outbox_worker.start()
    try:
        yield
    finally:
        outbox_worker.stop()

app = FastAPI(
    title="MarchéCI — Service Commandes",
    description="Passage et suivi des commandes (prix validés au niveau du service Catalogue).",
    version="1.0.0",
    lifespan=lifespan,
)

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "event",
        extra={
            "event": "http_access",
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        },
    )
    return response


app.include_router(health.router)
app.include_router(orders.router)
