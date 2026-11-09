"""Publication RabbitMQ de l'événement order.created (bonus asynchrone).

Résilience : si le broker est indisponible, la commande reste enregistrée
(règle métier documentée) et l'échec est tracé ; 3 tentatives avec backoff.
File dédiée : `order.created`, dead-lettering vers `order.created.dlq`.
"""

import json
import logging
import time
from typing import Any

import pika

from .config import get_settings

logger = logging.getLogger(__name__)


class OrderEventPublisher:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        exchange: str,
        queue: str,
        dlq: str,
        timeout: float = 3.0,
        max_retries: int = 3,
        retry_backoff_seconds: float = 2.0,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.exchange = exchange
        self.queue = queue
        self.dlq = dlq
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.enabled = True

    def _connect(self):
        credentials = pika.PlainCredentials(self.user, self.password)
        return pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                socket_timeout=self.timeout,
                blocked_connection_timeout=self.timeout,
            )
        )

    def _declare_topologie(self, channel) -> None:
        """Exchange + queue principale + DLQ. Idempotent : mêmes paramètres des deux côtés."""
        channel.exchange_declare(exchange=self.exchange, exchange_type="direct", durable=True)
        channel.queue_declare(queue=self.dlq, durable=True)
        args = {"x-dead-letter-exchange": self.exchange, "x-dead-letter-routing-key": self.dlq}
        channel.queue_declare(queue=self.queue, durable=True, arguments=args)
        channel.queue_bind(queue=self.queue, exchange=self.exchange, routing_key=self.queue)
        channel.queue_bind(queue=self.dlq, exchange=self.exchange, routing_key=self.dlq)
        for attempt in range(1, self.max_retries + 1):
            channel.queue_declare(
                queue=f"{self.queue}.retry.{attempt}",
                durable=True,
                arguments={
                    "x-message-ttl": int(self.retry_backoff_seconds * (2 ** (attempt - 1)) * 1000),
                    "x-dead-letter-exchange": self.exchange,
                    "x-dead-letter-routing-key": self.queue,
                },
            )

    def publish_order_created(self, event: dict[str, Any]) -> bool:
        """3 tentatives ; False si le broker reste injoignable (commande quand même créée)."""
        if not self.enabled:
            logger.info("event", extra={"event": "events_disabled_skip_publish"})
            return False
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")

        for attempt in range(1, 4):
            try:
                conn = self._connect()
                try:
                    channel = conn.channel()
                    self._declare_topologie(channel)
                    channel.confirm_delivery()
                    channel.basic_publish(
                        exchange=self.exchange,
                        routing_key=self.queue,
                        body=body,
                        mandatory=True,
                        properties=pika.BasicProperties(
                            content_type="application/json",
                            delivery_mode=2,  # durable
                            headers={"event": "order.created", "attempt": str(attempt)},
                        ),
                    )
                finally:
                    conn.close()
                logger.info(
                    "event",
                    extra={"event": "order_created_published", "order_id": event.get("order_id"), "attempt": attempt},
                )
                return True
            except Exception as exc:
                logger.warning("event", extra={"event": "publish_failed", "attempt": attempt, "detail": str(exc)})
                if attempt < 3:
                    time.sleep(2**attempt)  # 2 s puis 4 s
        return False
