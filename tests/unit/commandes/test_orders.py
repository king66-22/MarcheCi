"""Tests du service Commandes : création validée, stock, statuts, événements, résilience."""

import pytest
import jwt as pyjwt

from conftest import make_token

AUTH_CLIENT = {"Authorization": f"Bearer {make_token(10, 'CLIENT')}"}
AUTH_ADMIN = {"Authorization": f"Bearer {make_token(1, 'ADMIN')}"}

BASE_ORDER = {
    "items": [{"product_id": 1, "quantity": 2}],
    "delivery_address": "12 rue des Marchés, Adjamé, Abidjan",
    "delivery_phone": "0707070707",
}


@pytest.fixture(autouse=True)
def seed_products(fake_catalogue):
    fake_catalogue.set(1, "Attiéké Trésor 1kg", 12500, 100)
    fake_catalogue.set(2, "Café Robusta 500g", 4500, 10)
    fake_catalogue.set(3, "Pagne wax A", 15000, 2)


# -------------------------------- health --------------------------------


def test_health(client, monkeypatch):
    from types import SimpleNamespace
    from app.routers import health

    class Connection:
        def close(self):
            pass

    class HttpClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(health.pika, "BlockingConnection", lambda *a, **k: Connection())
    monkeypatch.setattr(health.httpx, "Client", HttpClient)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["components"]["database"] == "up"
    assert body["components"]["rabbitmq"] == "up"
    assert body["components"]["catalogue"] == "reachable"


def test_health_unhealthy_when_rabbitmq_auth_fails(client, monkeypatch):
    from app.routers import health

    class HttpClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return type("Response", (), {"status_code": 200})()

    monkeypatch.setattr(health.httpx, "Client", HttpClient)
    monkeypatch.setattr(health.pika, "BlockingConnection", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["components"]["rabbitmq"] == "down"


def test_health_unhealthy_when_catalogue_is_unreachable(client, monkeypatch):
    from app.routers import health

    class Connection:
        def close(self):
            pass

    monkeypatch.setattr(health.pika, "BlockingConnection", lambda *a, **k: Connection())
    class HttpClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): raise health.httpx.ConnectError("unreachable")

    monkeypatch.setattr(health.httpx, "Client", HttpClient)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["components"]["catalogue"] == "unreachable"


# ------------------------- création de commande -------------------------


def test_create_order_validates_prices_server_side(client, fake_catalogue, fake_publisher):
    """Le client pourrait envoyer n'importe veille : le prix est celui du catalogue (12500)."""
    resp = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total_xof"] == 12500 * 2  # calculé côté serveur
    assert body["status"] == "EN_ATTENTE"
    assert body["items"][0]["unit_price_xof"] == 12500
    assert body["items"][0]["product_name"] == "Attiéké Trésor 1kg"
    from sqlalchemy import select
    from app.database import get_db
    from app.models import OutboxEvent
    from app.outbox import run_once

    db = next(client.app.dependency_overrides[get_db]())
    try:
        event = db.scalar(select(OutboxEvent).order_by(OutboxEvent.id.desc()))
        assert event is not None and event.payload["order_id"] == body["id"]
        assert event.published_at is None
        assert run_once(db, fake_publisher) is True
        db.refresh(event)
        assert event.published_at is not None
        assert fake_publisher.published and fake_publisher.published[0]["event"] == "order.created"
    finally:
        db.close()


def test_create_order_requires_auth(client):
    assert client.post("/orders", json=BASE_ORDER).status_code == 401


def test_create_order_clean_sku_duplicates(client):
    dup = BASE_ORDER | {"items": [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}]}
    assert client.post("/orders", json=dup, headers=AUTH_CLIENT).status_code == 422


def test_create_order_stock_insufficient_409(client, fake_catalogue):
    resp = client.post("/orders", json=BASE_ORDER | {"items": [{"product_id": 3, "quantity": 5}]}, headers=AUTH_CLIENT)
    assert resp.status_code == 409
    # Stock du catalogue inchangé
    assert fake_catalogue.products[3]["stock"] == 2


def test_unknown_product_422(client):
    resp = client.post("/orders", json=BASE_ORDER | {"items": [{"product_id": 99, "quantity": 1}]}, headers=AUTH_CLIENT)
    assert resp.status_code == 422


def test_weak_payload_invalid(client):
    bad = BASE_ORDER | {"delivery_phone": "12"}
    assert client.post("/orders", json=bad, headers=AUTH_CLIENT).status_code == 422


def test_empty_items_422(client):
    assert client.post("/orders", json=BASE_ORDER | {"items": []}, headers=AUTH_CLIENT).status_code == 422


# ------------------------------ stock et compensation ------------------------------


def test_stock_decremented_after_order(client, fake_catalogue):
    client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    assert fake_catalogue.products[1]["stock"] == 98


def test_compensation_on_partial_stock_failure(client, fake_catalogue):
    """Le 2e ajustement échoue → le 1er décrément est restitué."""
    fake_catalogue.set(4, "Produit rare", 10000, 1)
    payload = {
        "items": [{"product_id": 1, "quantity": 2}, {"product_id": 4, "quantity": 3}],  # 4 : stock 1 < 3
        "delivery_address": "12 rue des Marchés, Adjamé, Abidjan",
        "delivery_phone": "0707070707",
    }
    resp = client.post("/orders", json=payload, headers=AUTH_CLIENT)
    assert resp.status_code == 409
    assert fake_catalogue.products[1]["stock"] == 100, "compensation non effective"


def test_catalogue_down_503_order_rejected(client, fake_catalogue):
    fake_catalogue.unavailable = True
    resp = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    assert resp.status_code == 503


def test_broker_down_order_still_created(client, fake_publisher):
    """Si RabbitMQ est en panne, la commande est quand même créée (règle documentée)."""
    fake_publisher.fail = True
    resp = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    assert resp.status_code == 201
    from sqlalchemy import select
    from app.database import get_db
    from app.models import OutboxEvent
    from app.outbox import run_once

    db = next(client.app.dependency_overrides[get_db]())
    try:
        event = db.scalar(select(OutboxEvent).order_by(OutboxEvent.id.desc()))
        assert event is not None and event.published_at is None
        assert event.attempts == 0
        assert run_once(db, fake_publisher) is False
        db.refresh(event)
        assert event.attempts >= 1
        fake_publisher.fail = False
        assert run_once(db, fake_publisher) is True
        db.refresh(event)
        assert event.published_at is not None
    finally:
        db.close()


# --------------------------- historique et accès ---------------------------


def test_user_sees_only_own_orders(client):
    client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    other = {"Authorization": f"Bearer {make_token(11, 'CLIENT')}"}
    body = client.get("/orders", headers=other).json()
    assert body["total"] == 0
    assert client.get("/orders", headers=AUTH_CLIENT).json()["total"] == 1


def test_admin_sees_all_orders(client):
    client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    body = client.get("/orders", headers=AUTH_ADMIN).json()
    assert body["total"] == 1


def test_order_access_detailed_permissions(client):
    resp = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT)
    oid = resp.json()["id"]
    other = {"Authorization": f"Bearer {make_token(11, 'CLIENT')}"}
    assert client.get(f"/orders/{oid}", headers=other).status_code == 403
    assert client.get(f"/orders/{oid}", headers=AUTH_ADMIN).status_code == 200


# ------------------------------- statuts --------------------------------


def test_status_transitions_happy_path(client):
    oid = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT).json()["id"]
    for next_status in ("CONFIRMEE", "EN_PREPARATION", "EXPEDIEE", "LIVREE"):
        resp = client.patch(f"/orders/{oid}/status", json={"status": next_status}, headers=AUTH_ADMIN)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == next_status


def test_status_transition_forbidden_paths(client):
    oid = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT).json()["id"]

    resp = client.patch(f"/orders/{oid}/status", json={"status": "LIVREE"}, headers=AUTH_ADMIN)
    assert resp.status_code == 409  # saut EN_ATTENTE → LIVREE interdit


def test_status_change_requires_admin(client):
    oid = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT).json()["id"]
    resp = client.patch(f"/orders/{oid}/status", json={"status": "CONFIRMEE"}, headers=AUTH_CLIENT)
    assert resp.status_code == 403


def test_cancel_restocks(client, fake_catalogue):
    oid = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT).json()["id"]
    assert fake_catalogue.products[1]["stock"] == 98
    resp = client.post(f"/orders/{oid}/cancel", headers=AUTH_CLIENT)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ANNULEE"
    assert fake_catalogue.products[1]["stock"] == 100  # stock restitué


def test_cancel_after_ship_forbidden(client):
    oid = client.post("/orders", json=BASE_ORDER, headers=AUTH_CLIENT).json()["id"]
    client.patch(f"/orders/{oid}/status", json={"status": "CONFIRMEE"}, headers=AUTH_ADMIN)
    client.patch(f"/orders/{oid}/status", json={"status": "EN_PREPARATION"}, headers=AUTH_ADMIN)
    resp = client.post(f"/orders/{oid}/cancel", headers=AUTH_CLIENT)
    assert resp.status_code == 409
