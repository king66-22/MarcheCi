"""Publication durable des événements enregistrés dans l'outbox."""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import OutboxEvent

logger = logging.getLogger(__name__)


def dispatch_one(session_factory=SessionLocal, publisher=None, session: Session | None = None) -> bool:
    """Publie le plus ancien événement en attente; True si rien ne reste à faire."""
    if publisher is None:
        from .services import get_publisher

        publisher = get_publisher()
    owns_session = session is None
    db: Session = session or session_factory()
    try:
        row = db.scalar(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return True
        row.attempts += 1
        try:
            delivered = publisher.publish_order_created(row.payload)
        except Exception as exc:
            delivered = False
            row.last_error = type(exc).__name__
            logger.exception("event", extra={"event": "outbox_publish_failed", "outbox_id": row.id})
        if delivered:
            row.published_at = datetime.now(UTC)
            row.last_error = None
        elif row.last_error is None:
            row.last_error = "broker_unavailable"
        db.commit()
        return bool(delivered)
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


class OutboxWorker:
    def __init__(self, interval_seconds: float = 2.0):
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="orders-outbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                dispatch_one()
            except Exception:
                logger.exception("event", extra={"event": "outbox_worker_error"})
            self._stop.wait(self.interval_seconds)


def run_once(db: Session, publisher) -> bool:
    """Variante injectée utilisée après création et par les tests transactionnels."""
    return dispatch_one(publisher=publisher, session=db)
