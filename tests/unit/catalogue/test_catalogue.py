"""Tests fonctionnels endpoints publics + gestion ADMIN + auth + stock + cache du catalogue."""

import io
import os
import time
from pathlib import Path

import jwt as pyjwt
import pytest
from PIL import Image

SERCRET = "test-secret"  # aligné avec conftest


def jwt_for(role: str = "ADMIN", sub: str = "1") -> str:
    import time as _t

    payload = {
        "sub": sub,
        "role": role,
        "exp": int(_t.time()) + 3600,
        "iss": "marcheci",
        "aud": "marcheci",
    }
    return pyjwt.encode(payload, SERCRET, algorithm="HS256")


AUTH_ADMIN = {"Authorization": f"Bearer {jwt_for('ADMIN')}"}
AUTH_CLIENT = {"Authorization": f"Bearer {jwt_for('CLIENT', sub='42')}"}
AUTH_MERCHANT = {"Authorization": f"Bearer {jwt_for('COMMERCANT', sub='7')}"}
AUTH_MERCHANT_2 = {"Authorization": f"Bearer {jwt_for('COMMERCANT', sub='8')}"}

PRODUCT = {"slug": "attieke", "name": "Attiéké", "price_xof": 1500, "stock": 10}


def png_bytes(size: tuple[int, int] = (1200, 900)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 80, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def seeded_category(client):
    """Crée une catégorie via l'instance SQL directe."""
    from app.database import get_db
    from app.models import Category

    session = next(client.app.dependency_overrides[get_db]())
    cat = Category(slug="cereales", name="Céréales")
    session.add(cat)
    session.commit()
    session.close()


# ------------------------------- santé --------------------------------


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["components"]["database"] == "up"


# ----------------------------- public API -----------------------------


def test_products_empty(client):
    resp = client.get("/products")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == [] and body["total"] == 0


def test_create_and_get_product(client_auth, seeded_category):
    payload = {
        "slug": "attieke-tresor-1kg",
        "name": "Attiéké Trésor 1kg",
        "description": "Semoule de manioc ivoirienne",
        "price_xof": 12500,
        "category_id": 1,
        "stock": 30,
    }
    resp = client_auth.post("/products", json=payload, headers=AUTH_ADMIN)
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["id"] == 1 and created["is_active"] is True

    detail = client_auth.get("/products/1")
    assert detail.status_code == 200
    assert detail.json()["price_xof"] == 12500
    assert detail.json()["category_slug"] == "cereales"


def test_price_floating_rejected(client_auth):
    resp = client_auth.post(
        "/products",
        json={"slug": "p", "name": "P", "price_xof": 9999.5, "stock": 1},
        headers=AUTH_ADMIN,
    )
    assert resp.status_code == 422


def test_list_pagination_and_filters(client_auth):
    for i in range(5):
        client_auth.post(
            "/products",
            json={"slug": f"p{i}", "name": f"Produit {i}", "price_xof": 1000 + i, "stock": i},
            headers=AUTH_ADMIN,
        )
    all_products = client_auth.get("/products").json()
    assert all_products["total"] == 5
    page = client_auth.get("/products?page=2&page_size=2").json()
    assert len(page["items"]) == 2

    search = client_auth.get("/products?q=produit 3").json()
    assert search["total"] == 1

    stocked = client_auth.get("/products?in_stock=true").json()
    assert all(item["stock"] > 0 for item in stocked["items"])


def test_inactive_product_hidden(client_auth):
    client_auth.post("/products", json={"slug": "x", "name": "X", "price_xof": 5}, headers=AUTH_ADMIN)
    client_auth.delete("/products/1", headers=AUTH_ADMIN)  # soft-delete
    assert client_auth.get("/products").json()["total"] == 0
    assert client_auth.get("/products/1").status_code == 404


# --------------------------- autorisations ---------------------------


def test_create_product_requires_auth(client):
    resp = client.post("/products", json={"slug": "a", "name": "A", "price_xof": 1})
    assert resp.status_code == 401


def test_create_product_requires_admin_role(client):
    resp = client.post(
        "/products",
        json={"slug": "a", "name": "A", "price_xof": 1},
        headers=AUTH_CLIENT,
    )
    assert resp.status_code == 403


def test_bad_token(client):
    resp = client.post("/products", json={}, headers={"Authorization": "Bearer not-a-token"})
    assert resp.status_code == 401


# ------------------------- espace commerçant -------------------------


def test_merchant_creates_owned_product(client):
    resp = client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)
    assert resp.status_code == 201, resp.text
    assert resp.json()["owner_id"] == 7


def test_merchant_cannot_manage_another_product(client):
    client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)

    update = client.put("/products/1", json={"price_xof": 999}, headers=AUTH_MERCHANT_2)
    assert update.status_code == 403
    delete = client.delete("/products/1", headers=AUTH_MERCHANT_2)
    assert delete.status_code == 403
    # L'ADMIN conserve le droit d'intervention.
    assert client.put("/products/1", json={"price_xof": 999}, headers=AUTH_ADMIN).status_code == 200


def test_products_mine_isolation(client):
    client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)
    client.post(
        "/products",
        json={"slug": "autre", "name": "Autre", "price_xof": 500, "stock": 2},
        headers=AUTH_MERCHANT_2,
    )

    mine = client.get("/products/mine", headers=AUTH_MERCHANT)
    assert mine.status_code == 200
    body = mine.json()
    assert body["total"] == 1
    assert body["items"][0]["owner_id"] == 7
    assert body["items"][0]["slug"] == "attieke"


def test_client_cannot_access_merchant_space(client):
    client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)
    assert client.get("/products/mine", headers=AUTH_CLIENT).status_code == 403


def test_upload_image_and_cover(client):
    client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)

    first = client.post(
        "/products/1/images",
        files={"file": ("photo.png", png_bytes(), "image/png")},
        headers=AUTH_MERCHANT,
    )
    assert first.status_code == 201, first.text
    first_image = first.json()
    assert first_image["url"].startswith("/media/products/")

    stored = Path(os.environ["MEDIA_ROOT"]) / "products" / first_image["url"].rsplit("/", 1)[-1]
    assert stored.is_file()
    # La première photo devient la couverture.
    detail = client.get("/products/1").json()
    assert detail["image_url"] == first_image["url"]
    assert len(detail["images"]) == 1

    second = client.post(
        "/products/1/images",
        files={"file": ("photo2.png", png_bytes((600, 600)), "image/png")},
        headers=AUTH_MERCHANT,
    )
    assert second.status_code == 201
    second_image = second.json()
    assert client.post(
        f"/products/1/images/{second_image['id']}/cover", headers=AUTH_MERCHANT
    ).status_code == 200
    assert client.get("/products/1").json()["image_url"] == second_image["url"]

    deleted = client.delete(
        f"/products/1/images/{second_image['id']}", headers=AUTH_MERCHANT
    )
    assert deleted.status_code == 200
    detail = client.get("/products/1").json()
    assert detail["image_url"] == first_image["url"]
    assert len(detail["images"]) == 1


def test_upload_requires_owner_and_image(client):
    client.post("/products", json=PRODUCT, headers=AUTH_MERCHANT)

    assert client.post(
        "/products/1/images",
        files={"file": ("photo.png", png_bytes(), "image/png")},
        headers=AUTH_MERCHANT_2,
    ).status_code == 403

    assert client.post(
        "/products/1/images",
        files={"file": ("notes.txt", b"pas une image", "text/plain")},
        headers=AUTH_MERCHANT,
    ).status_code == 422

    assert client.post(
        "/products/1/images",
        files={"file": ("faux.png", b"contenu invalide", "image/png")},
        headers=AUTH_MERCHANT,
    ).status_code == 422


def test_image_url_accepts_media_path(client):
    payload = {**PRODUCT, "image_url": "/media/products/photo.jpg"}
    assert client.post("/products", json=payload, headers=AUTH_MERCHANT).status_code == 201
    payload = {**PRODUCT, "slug": "x", "image_url": "javascript:alert(1)"}
    assert client.post("/products", json=payload, headers=AUTH_MERCHANT).status_code == 422


# ------------------------------ stock --------------------------------


def test_adjust_stock_scenarios(client_auth):
    client_auth.post("/products", json={"slug": "s", "name": "S", "price_xof": 10, "stock": 5}, headers=AUTH_ADMIN)

    # Décrément OK
    r = client_auth.post("/products/1/adjust-stock", json={"delta": -2}, headers=AUTH_ADMIN)
    assert r.status_code == 200 and r.json()["stock_after"] == 3

    # Décrément responsable d'un stock négatif : 409
    r = client_auth.post("/products/1/adjust-stock", json={"delta": -10}, headers=AUTH_ADMIN)
    assert r.status_code == 409
    # Restitution
    r = client_auth.post("/products/1/adjust-stock", json={"delta": +10}, headers=AUTH_ADMIN)
    assert r.json()["stock_after"] == 13


# ------------------------------- cache (TTL 60 s) -------------------------------


def test_cache_hit_and_ttl(client_auth, cache):
    import fakeredis
    from fakeredis import FakeStrictRedis

    # Utiliser le faux redis pour la visite TTL : TTL 60s
    fake = cache
    client_auth.post("/products", json={"slug": "c1", "name": "C1", "price_xof": 10}, headers=AUTH_ADMIN)

    # Premier appel : MISS puis HIT, grâce au cache activé par la fixture
    res1 = client_auth.get("/products")
    assert res1.headers["X-Cache"] == "MISS"
    res2 = client_auth.get("/products")
    assert res2.headers["X-Cache"] == "HIT"

    # Clés correspondantes présentes, TTL plafonné à 60 s
    keys = list(fake.scan_iter("products:list:*"))
    assert keys, "aucune clé de cache"
    ttl = int(fake.ttl(keys[0]))
    assert 0 < ttl <= 60, f"TTL cache invalide : {ttl}"


def test_cache_invalidated_after_update(client_auth, cache):
    fake = cache
    client_auth.post("/products", json={"slug": "c2", "name": "C2", "price_xof": 10}, headers=AUTH_ADMIN)
    client_auth.get("/products")  # remplit le cache
    client_auth.get("/products")
    keys = list(fake.scan_iter("products:list:*"))
    assert keys
    client_auth.put("/products/1", json={"price_xof": 999}, headers=AUTH_ADMIN)
    assert not list(fake.scan_iter("products:list:*")), "cache non invalidé après update"
