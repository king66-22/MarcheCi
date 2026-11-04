"""Tests d'intégration réels : parcours complet d'achat à travers les microservices.

Catalogue, utilisateurs, commandes, notifications sont d'authentiques processus
uvicorn distincts, chacun **sa base SQLite**, communication HTTP réelle.
"""

import httpx
import pytest

from conftest import h


def test_users_connect(stack, auth_tokens):
    """Connexion réelle via le service utilisateurs."""
    r = httpx.get(f"{stack['utilisateurs']}/users/me", headers=h(auth_tokens["client"]), timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == "client@example.ci"
    r = httpx.get(f"{stack['utilisateurs']}/users/me", headers=h(auth_tokens["admin"]), timeout=10)
    assert r.status_code == 200
    assert r.json()["role"] == "ADMIN"


def test_full_purchase_flow(stack, auth_tokens):
    """Admin : catégories/produits ; Client : commande ; stock décrémenté/restauré."""
    cat, cmd = stack["catalogue"], stack["commandes"]

    # (b) Admin crée catégories + produits
    r = httpx.post(f"{cat}/categories", json={"slug": "cereales", "name": "Céréales"}, headers=h(auth_tokens["admin"]), timeout=10)
    assert r.status_code in (201, 409), r.text
    r = httpx.post(
        f"{cat}/products",
        json={"slug": "attieke-tresor-1kg", "name": "Attiéké Trésor 1kg", "description": "Manioc fermenté", "price_xof": 12500, "stock": 100, "category_id": 1},
        headers=h(auth_tokens["admin"]), timeout=10,
    )
    assert r.status_code in (201, 409), r.text
    product_id = r.json()["id"] if r.status_code == 201 else 1

    # (c) Le client consulte le catalogue (API publique, recherche sans tréma)
    r = httpx.get(f"{cat}/products?q=Attiéké", timeout=10)
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # (d) Commande réelle : prix validés CÔTÉ SERVEUR par le catalogue
    r = httpx.post(
        f"{cmd}/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "delivery_address": "12 rue des Marchés, Adjamé",
            "delivery_phone": "0707070707",
        },
        headers=h(auth_tokens["client"]), timeout=15,
    )
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["total_xof"] == 25000  # 2 x 12500 (prix du catalogue)
    assert order["status"] == "EN_ATTENTE"
    oid = order["id"]

    # (f) Stock décrémenté côté catalogue
    r = httpx.get(f"{cat}/products/{product_id}", timeout=10)
    assert r.json()["stock"] == 98

    # (g) Annulation par le client → stock restitué par heure
    r = httpx.post(f"{cmd}/orders/{oid}/cancel", headers=h(auth_tokens["client"]), timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ANNULEE"
    r = httpx.get(f"{cat}/products/{product_id}", timeout=10)
    assert r.json()["stock"] == 100


def test_order_status_machine(stack, auth_tokens):
    cat, cmd = stack["catalogue"], stack["commandes"]

    httpx.post(
        f"{cat}/products",
        json={"slug": "cafe-robusta-500g", "name": "Café Robusta 500g", "price_xof": 4500, "stock": 10},
        headers=h(auth_tokens["admin"]), timeout=10,
    )

    r = httpx.post(
        f"{cmd}/orders",
        json={
            "items": [{"product_id": 2, "quantity": 1}],
            "delivery_address": "45 avenue Chardy, Treichville",
            "delivery_phone": "0101010101",
        },
        headers=h(auth_tokens["client"]), timeout=15,
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]

    # Transitions normales par l'ADMIN
    for st in ("CONFIRMEE", "EN_PREPARATION"):
        r = httpx.patch(f"{cmd}/orders/{oid}/status", json={"status": st}, headers=h(auth_tokens["admin"]), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == st

    # Saut EN_PREPARATION→LIVREE interdit (machine à états)
    r = httpx.patch(f"{cmd}/orders/{oid}/status", json={"status": "LIVREE"}, headers=h(auth_tokens["admin"]), timeout=10)
    assert r.status_code == 409


def test_client_cannot_use_admin_features(stack, auth_tokens):
    cat = stack["catalogue"]
    r = httpx.post(
        f"{cat}/products",
        json={"slug": "hack-produit", "name": "Hack", "price_xof": 1},
        headers=h(auth_tokens["client"]), timeout=10,
    )
    assert r.status_code == 403


def test_price_cannot_be_forged(stack, auth_tokens):
    """Exigence : ne JAMAIS faire confiance au prix du navigateur."""
    cmd = stack["commandes"]

    # Le client tente d'envoyer une « price_xof » bidon dans le payload (champ ignoré)
    r = httpx.post(
        f"{cmd}/orders",
        json={
            "items": [{"product_id": 1, "quantity": 2, "unit_price_xof": 1}],
            "delivery_address": "12 rue des Marchés, Adjamé",
            "delivery_phone": "0707070707",
        },
        headers=h(auth_tokens["client"]), timeout=15,
    )
    assert r.status_code == 201
    # total calculé avec les prix réels du catalogue
    assert r.json()["total_xof"] == 25000


def test_catalogue_down_orders_fail_cleanly(stack, auth_tokens):
    """Résilience de base : catalogue indisponible → 503 propre, aucune commande créée."""
    broken = stack["commandes_broken"]
    r = httpx.post(
        f"{broken}/orders",
        json={
            "items": [{"product_id": 1, "quantity": 1}],
            "delivery_address": "12 rue des Marchés, Adjamé",
            "delivery_phone": "0707070707",
        },
        headers=h(auth_tokens["client"]), timeout=30,
    )
    assert r.status_code == 503, r.text
    votes = httpx.get(f"{broken}/orders", headers=h(auth_tokens["client"]), timeout=10)
    assert votes.json()["total"] == 0


def test_notifications_health_and_protection(stack):
    ntf = stack["notifications"]
    r = httpx.get(f"{ntf}/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["components"]["database"] == "up"
    assert body["components"]["consumer"] == "down"  # RabbitMQ absent (sans Docker), documenté
    assert httpx.get(f"{ntf}/notifications", timeout=10).status_code == 401
