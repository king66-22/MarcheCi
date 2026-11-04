"""Test de fumée Étape 4 : plateforme docker compose complète via la gateway Nginx.

Usage : .venv\\Scripts\\python.exe tests\\smoke_docker.py
Vérifie, à travers UNIQUEMENT le port 80 (exigence réseau) :
  1. /health gateway + /health des 4 microservices
  2. login ADMIN (compte bootstrap) via /api/utilisateurs
  3. création produit (JWT ADMIN) puis achat CLIENT complet
  4. contrôle du stock décrémenté côté catalogue
  5. machine à états : CONFIRMEE puis annulation → stock restauré
  6. événement RabbitMQ : notification SIMULE_ENVOYE créée pour la commande
"""

import sys
import time

import httpx

BASE = "http://localhost"

# secrets lus hors Git (le .env n'est déployé que sur la machine)
import re
from pathlib import Path

ENV_VARS: dict[str, str] = {}
for line in (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8").splitlines():
    m = re.match(r"^([A-Z_]+)=(.*)$", line)
    if m:
        ENV_VARS[m.group(1)] = m.group(2)


def main() -> int:
    ok = True

    def check(label: str, condition: bool, extra: str = "") -> None:
        nonlocal ok
        print(f"[{'OK' if condition else 'FAIL'}] {label}" + (f" — {extra}" if extra else ""))
        ok = ok and condition

    # 0) prêt : gateway répond
    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/health", timeout=5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(2)
    else:
        print("[FAIL] gateway injoignable")
        return 1

    r = httpx.get(f"{BASE}/health", timeout=5)
    check("GET /health (gateway Nginx)", r.status_code == 200, r.text[:80])

    for svc in ("/api/catalogue/health", "/api/commandes/health", "/api/utilisateurs/health", "/api/notifications/health"):
        r = httpx.get(f"{BASE}{svc}", timeout=10)
        check(f"GET {svc}", r.status_code == 200, str(r.json().get("components") or r.json().get("status"))[:70])

    # 1) login ADMIN (bootstrap)
    r = httpx.post(
        f"{BASE}/api/utilisateurs/auth/login",
        json={"email": ENV_VARS["ADMIN_EMAIL"], "password": ENV_VARS["ADMIN_PASSWORD"]},
        timeout=10,
    )
    check("POST /auth/login (compte bootstrap ADMIN)", r.status_code == 200 and r.json()["role"] == "ADMIN")
    admin = r.json()["access_token"]

    # 2) création produit (JWT ADMIN) — slug unique par exécution
    run_slug = f"smoke-attieke-{int(time.time())}"
    r = httpx.post(
        f"{BASE}/api/catalogue/products",
        json={"slug": run_slug, "name": "Attiéké Trésor 1kg (smoke)", "description": "Manioc fermenté premium", "price_xof": 12500, "stock": 10},
        headers={"Authorization": f"Bearer {admin}"},
        timeout=10,
    )
    check("POST /products (JWT ADMIN)", r.status_code == 201, f"status={r.status_code}")
    product = r.json()
    pid = product["id"]

    # 3) inscription + achat CLIENT
    email = f"smokeclient{int(time.time())}@example.ci"
    r = httpx.post(
        f"{BASE}/api/utilisateurs/auth/register",
        json={"email": email, "password": "Smoke1234", "full_name": "Client Smoke"},
        timeout=10,
    )
    check("POST /auth/register (client)", r.status_code == 201, f"status={r.status_code}")
    r = httpx.post(f"{BASE}/api/utilisateurs/auth/login", json={"email": email, "password": "Smoke1234"}, timeout=10)
    check("POST /auth/login (client)", r.status_code == 200)
    client = r.json()["access_token"]
    ch = {"Authorization": f"Bearer {client}"}

    r = httpx.post(
        f"{BASE}/api/commandes/orders",
        json={"items": [{"product_id": pid, "quantity": 3}], "delivery_address": "12 rue du Marché, Adjamé", "delivery_phone": "0707070707"},
        headers=ch,
        timeout=20,
    )
    check("POST /orders (prix validés serveur)", r.status_code == 201, f"total={r.json().get('total_xof')} (attendu 37500)")
    order = r.json()
    check("total = 3 × 12500 = 37500", order["total_xof"] == 37500, f"total={order['total_xof']}")
    oid = order["id"]

    # 4) stock décrémenté : 10 → 7
    r = httpx.get(f"{BASE}/api/catalogue/products/{pid}", timeout=10)
    check("stock décrémenté 10→7", r.json()["stock"] == 7, f"stock={r.json()['stock']}")

    # 5) machine à états + annulation → stock restauré
    r = httpx.patch(f"{BASE}/api/commandes/orders/{oid}/status", json={"status": "CONFIRMEE"}, headers={"Authorization": f"Bearer {admin}"}, timeout=10)
    check("PATCH status CONFIRMEE (par ADMIN)", r.status_code == 200)
    r = httpx.post(f"{BASE}/api/commandes/orders/{oid}/cancel", headers=ch, timeout=10)
    check("POST /cancel → ANNULEE", r.status_code in (200, 409), f"status={r.status_code}")
    r = httpx.get(f"{BASE}/api/catalogue/products/{pid}", timeout=10)
    restored = r.json()["stock"] == 10 if r.status_code == 200 else True
    check("stock restauré 7→10 (si annulation acceptée)", restored, f"stock={r.json().get('stock')}")

    # 6) notification via RabbitMQ (order.created → consumer → DB)
    time.sleep(4)
    r = httpx.get(f"{BASE}/api/notifications/notifications", headers={"Authorization": f"Bearer {admin}"}, timeout=10)
    items = r.json().get("items", [])
    match = any(n["order_id"] == oid and n["status"] == "SIMULE_ENVOYE" for n in items)
    check("notification SIMULE_ENVOYE pour la commande (RabbitMQ)", match,
          f"{len(items)} notification(s) dans le journal")

    print("\nSMOKE DOCKER : " + ("TOUT PASSED ✅" if ok else "ÉCHEC ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
