"""Consommateur RabbitMQ du service Notifications.

Stratégie de fiabilité :
- messages non-JSON ou incomplets → rejet sans requeue → **DLQ** (`order.created.dlq`) ;
- erreurs transitoires → republication dans la même file avec un header `x-retry`
  et un TTL d'attente, jusqu'à `consumer_max_retries`, puis DLQ ;
- tout envoi est **SIMULÉ** (aucun fournisseur email/SMS configuré) : statut
  `SIMULE_ENVOYE` en base + log explicite.
"""

import json
import logging
import threading
import time
from typing import Any

import pika

from .config import get_settings
from .database import get_db_session
from .models import Notification, STATUS_SIMULATED

logger = logging.getLogger(__name__)


# ---------------------------- Logique métier ----------------------------


def event_to_notification(event: dict[str, Any]) -> dict[str, Any]:
    """Transforme un payload `order.created` en notification enregistrée."""
    try:
        order_id = int(event["order_id"])
        user_id = int(event["user_id"])
        total = int(event["total_xof"])
        items = event["items"]
        if not isinstance(items, list) or not items:
            raise ValueError("items manquants")
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Événement illisible : {exc}") from exc

    recipient = event.get("user_email") or f"client-{user_id}@marcheci.inconnu"
    notification_data = {
        "order_id": order_id,
        "user_id": user_id,
        "channel": "EMAIL",
        "recipient": recipient,
        "template": "order_confirmation",
        "status": STATUS_SIMULATED,
        "payload": event,
        "attempts": 1,
    }
    # Simulation explicite de l'envoi (aucun fournisseur configuré)
    logger.info(
        "event",
        extra={
            "event": "simulated_send",
            "order_id": order_id,
            "detail": f"Envoi EMAIL SIMULÉ de la confirmation à {recipient} (total {total} FCFA)",
        },
    )
    return notification_data


class EventConsumer:
    """Consommateur avec reconnect, retries + DLQ. Exécutable en thread de fond."""

    def __init__(self, url_params: dict[str, Any], queue: str, dlq: str, exchange: str, max_retries: int = 3, backoff: float = 2.0):
        self.queue = queue
        self.dlq = dlq
        self.exchange = exchange
        self.max_retries = max_retries
        self.backoff = backoff
        self._params = url_params
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="notifications-consumer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ----------------------- Boucle principale -----------------------

    def _run_loop(self) -> None:
        retry_delay = get_settings().consumer_reconnect_seconds
        while not self._stop.is_set():
            try:
                self._run_once()
            except Exception as exc:
                self.last_error = str(exc)
                logger.warning("event", extra={"event": "consumer_restart", "detail": str(exc)})
                self._stop.wait(retry_delay)

    def _run_once(self) -> None:
        conn = pika.BlockingConnection(pika.ConnectionParameters(**self._params))
        try:
            channel = conn.channel()
            self._declare_topologie(channel)
            channel.basic_qos(prefetch_count=10)
            channel.basic_consume(
                queue=self.queue,
                on_message_callback=self._handle,
                auto_ack=False,
            )
            logger.info("event", extra={"event": "consumer_started", "detail": f"queue={self.queue}"})
            # Bloque le thread du consommateur ; une erreur réseau/remontée repartira dans _run_loop
            channel.start_consuming()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _declare_topologie(self, channel) -> None:
        channel.exchange_declare(exchange=self.exchange, exchange_type="direct", durable=True)
        channel.queue_declare(queue=self.dlq, durable=True)
        args = {"x-dead-letter-exchange": self.exchange, "x-dead-letter-routing-key": self.dlq}
        channel.queue_declare(queue=self.queue, durable=True, arguments=args)
        channel.queue_bind(queue=self.queue, exchange=self.exchange, routing_key=self.queue)
        channel.queue_bind(queue=self.dlq, exchange=self.exchange, routing_key=self.dlq)

    # ----------------------------- Gestion d'un message -----------------------------

    def _handle(self, channel, method, properties, body):
        attempt = int((properties.headers or {}).get("x-retry", 0)) + 1
        try:
            event = json.loads(body)
        except ValueError:
            self._reject_to_dlq(channel, method, body, "payload non-JSON")
            return

        if event.get("event") != "order.created":
            self._reject_to_dlq(channel, method, body, f"type d'event inattendu {event.get('event')!r}")
            return

        try:
            with get_db_session() as db:
                notification = Notification(**event_to_notification(event))
                db.add(notification)
                db.commit()
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except ValueError as exc:
            self._reject_to_dlq(channel, method, body, str(exc))
            return
        except Exception as exc:
            # Erreur transitoire (BDD/indispo) : retry limité, sinon DLQ
            self.last_error = str(exc)
            if attempt <= self.max_retries:
                delay_ms = int(self.backoff * (attempt) * 1000)
                channel.basic_publish(
                    exchange="",
                    routing_key=self.queue,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type="application/json", delivery_mode=2,
                        headers={"x-retry": attempt}, expiration=str(delay_ms),
                    ),
                )
                channel.basic_ack(delivery_tag=method.delivery_tag)  # ack l'original ; duplicate republié séparément
                logger.warning(
                    "event",
                    extra={"event": "retry_scheduled", "attempt": attempt, "order_id": (event or {}).get("order_id")},
                )
            else:
                self._reject_to_dlq(channel, method, body, f"max retries depuis {self.max_retries} : {exc}")

    def _reject_to_dlq(self, channel, method, body: bytes, reason: str) -> None:
        self.last_error = reason
        # Copie vers la DLQ (routing par défaut) + ack du message original
        channel.basic_publish(
            exchange="",
            routing_key=self.dlq,
            body=body,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2, headers={"reason": reason}),
        )
        channel.basic_ack(delivery_tag=method.delivery_tag)
        logger.warning(
            "event",
            extra={"event": "message_to_dlq", "detail": reason},
        )


# Référence du consommateur actif (utilisée par le healthcheck) — déclarée après la classe
_active_consumer: EventConsumer | None = None


def set_active_consumer(consumer: EventConsumer | None) -> None:
    global _active_consumer
    _active_consumer = consumer


def get_active_consumer() -> EventConsumer | None:
    return _active_consumer
