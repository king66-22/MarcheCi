"""Point d'entrée FastAPI du service Notifications (consomateur RabbitMQ en thread)."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .consumer import EventConsumer, get_active_consumer, set_active_consumer  # noqa: F401
from .database import Base
from .logging_config import setup_logging
from .routers import monitor

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="MarchéCI — Service Notifications",
    description="Consommation des événements de commande (email/SMS SIMULÉ).",
    version="1.0.0",
)

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET"],
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


# ------------------------- Consommateur RabbitMQ -------------------------

from .database import engine  # noqa: E402 (après config init)
import pika  # noqa: E402


def build_consumer() -> EventConsumer:
    return EventConsumer(
        url_params={
            "host": settings.rabbitmq_host,
            "port": settings.rabbitmq_port,
            "credentials": pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password),
            "socket_timeout": 5,
            "heartbeat": 60,
            "blocked_connection_timeout": 5,
        },
        queue=settings.orders_queue,
        dlq=settings.orders_dlq,
        exchange=settings.rabbitmq_exchange,
        max_retries=settings.consumer_max_retries,
        backoff=settings.consumer_retry_backoff_seconds,
    )


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.events_enabled:
        consumer = build_consumer()
        consumer.start()
        set_active_consumer(consumer)
        logger.info("event", extra={"event": "service_started"})


@app.on_event("shutdown")
def shutdown() -> None:
    consumer = get_active_consumer()
    if consumer is not None:
        consumer.stop()


app.include_router(monitor.router)
