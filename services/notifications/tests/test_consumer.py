"""Tests notifications : transformation d'événements, DLQ/retries, API admin, health."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.consumer import EventConsumer, event_to_notification
from app.database import Base, engine
from app.models import Notification

from conftest import ADMIN


VALID_EVENT = {
    "event": "order.created",
    "order_id": 7,
    "user_id": 10,
    "total_xof": 28000,
    "status": "EN_ATTENTE",
    "user_email": "mariam@example.ci",
    "items": [{"product_id": 1, "quantity": 2, "unit_price_xof": 14000, "product_name": "P"}],
}


# --------------------------- logique métier ---------------------------


def test_event_to_notification_shape():
    data = event_to_notification(VALID_EVENT)
    assert data["order_id"] == 7
    assert data["recipient"] == "mariam@example.ci"
    assert data["status"] == "SIMULE_ENVOYE"  # simulation explicite exigée
    assert data["channel"] == "EMAIL"
    assert data["template"] == "order_confirmation"


def test_invalid_event_raises():
    with pytest.raises(ValueError):
        event_to_notification({"event": "order.created"})  # champs manquants


# --------------------------- API consultation ---------------------------


def test_notifications_requires_admin(client):
    assert client.get("/notifications").status_code == 401


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["components"]["database"] == "up"


def test_list_notifications_admin(client, db_session):
    db_session.add(Notification(**event_to_notification(VALID_EVENT)))
    db_session.add(Notification(**event_to_notification(VALID_EVENT | {"order_id": 8})))
    db_session.commit()

    resp = client.get("/notifications", headers=ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert all(n["status"] == "SIMULE_ENVOYE" for n in body["items"])


# --------------------- consommateur : gestion des messages ---------------------


class FakeChannel:
    """Pika channel minimal : enregistre ack/nack/publications."""

    def __init__(self):
        self.acked: list[tuple] = []
        self.published: list[dict] = []

    def basic_ack(self, delivery_tag):
        self.acked.append(("ack", delivery_tag))

    def basic_nack(self, delivery_tag, requeue):
        self.acked.append(("nack", delivery_tag, requeue))

    def basic_publish(self, **kwargs):
        self.published.append(kwargs)


class FakeMethod:
    def __init__(self, delivery_tag=1):
        self.delivery_tag = delivery_tag


class FakeProps:
    def __init__(self, headers=None):
        self.headers = headers or {}


def consume(consumer: EventConsumer, channel, body, headers=None, tag=1):
    consumer._handle(channel, FakeMethod(tag), FakeProps(headers), body)


@pytest.fixture()
def consumer_db(monkeypatch):
    """Injecte une session de test dans le consommateur (module app.consumer)."""
    TestingSession = sessionmaker(
        bind=create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    )
    TestingSession_default = TestingSession()
    Base.metadata.create_all(TestingSession_default.bind)
    TestingSession_default.commit()
    TestingSession_default.close()

    monkeypatch.setattr("app.consumer.get_db_session", TestingSession)
    yield TestingSession
    monkeypatch.undo()


def test_consumer_processes_valid_event(consumer_db):
    consumer = EventConsumer({}, queue="q", dlq="d", exchange="e")
    ch = FakeChannel()
    consume(consumer, ch, json.dumps(VALID_EVENT).encode())

    with consumer_db() as db:
        rows = db.query(Notification).all()
    assert len(rows) == 1 and rows[0].order_id == 7
    assert ("ack", 1) in [(a[0], a[1]) for a in ch.acked]
    assert ch.published == []


def test_consumer_sends_non_json_to_dlq(consumer_db):
    consumer = EventConsumer({}, queue="q", dlq="d", exchange="e")
    ch = FakeChannel()
    consume(consumer, ch, b"not-json$$$")
    with consumer_db() as db:
        assert db.query(Notification).count() == 0
    assert any(p["routing_key"] == "d" for p in ch.published)


def test_consumer_delegates_unknown_event_type_to_dlq(consumer_db):
    consumer = EventConsumer({}, queue="q", dlq="d", exchange="e")
    ch = FakeChannel()
    consume(consumer, ch, json.dumps({"event": "order.deleted", "order_id": 1}).encode())
    with consumer_db() as db:
        assert db.query(Notification).count() == 0
    assert any(p["routing_key"] == "d" for p in ch.published)


def test_consumer_transient_failure_retries_then_dlq(consumer_db, monkeypatch):
    """Erreur transitoire → republication retry (attempt inc.) ; au-delà → DLQ."""
    consumer = EventConsumer({}, queue="q", dlq="d", exchange="e", max_retries=1, backoff=0.0)

    class BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def add(self, *a):
            raise ConnectionError("transient DB unavailable")

        def commit(self):
            raise ConnectionError("transient DB unavailable")

    monkeypatch.setattr("app.consumer.get_db_session", BrokenSession)

    body = json.dumps(VALID_EVENT).encode()

    # 1re arrivée : retry planifié (republication dans q + ack original)
    ch = FakeChannel()
    consume(consumer, ch, body, headers={"x-retry": 0})
    assert any(p["routing_key"] == "q" for p in ch.published), "doit être replanifié"
    assert not any(p["routing_key"] == "d" for p in ch.published)

    # Tentative finale (x-retry=1 = max) : va en DLQ
    ch2 = FakeChannel()
    consume(consumer, ch2, body, headers={"x-retry": 1})
    assert any(p["routing_key"] == "d" for p in ch2.published), "doit finir en DLQ"
