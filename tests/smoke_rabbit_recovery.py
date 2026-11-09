"""Vérifie la reprise outbox après une panne RabbitMQ sur marcheci-e2e uniquement."""

import os
from pathlib import Path
import subprocess
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "marcheci-e2e"
BASE = os.environ.get("MARCHECI_BASE_URL", "http://localhost:8181").rstrip("/")


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT, *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()

    with httpx.Client(base_url=BASE, timeout=10) as client:
        admin = client.post(
            "/api/utilisateurs/auth/login",
            json={"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]},
        )
        admin.raise_for_status()
        admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
        products = client.get("/api/catalogue/products?page_size=100", headers=admin_headers)
        products.raise_for_status()
        product = next((p for p in products.json()["items"] if p["stock"] > 0), None)
        check(product is not None, "aucun produit test avec stock disponible")

        email = f"recovery-{time.time_ns()}@example.ci"
        created = client.post(
            "/api/utilisateurs/auth/register",
            json={"email": email, "password": "Recovery1234", "full_name": "Recovery test"},
        )
        created.raise_for_status()
        user = client.post(
            "/api/utilisateurs/auth/login",
            json={"email": email, "password": "Recovery1234"},
        )
        user.raise_for_status()
        user_headers = {"Authorization": f"Bearer {user.json()['access_token']}"}

    # PROJECT is deliberately fixed to the isolated Compose project.
    docker("stop", "rabbitmq")
    try:
        deadline = time.monotonic() + 45
        command_down = False
        health_probe = (
            "import httpx; r=httpx.get('http://127.0.0.1:8000/health',timeout=4); "
            "print(r.status_code, r.json().get('components',{}).get('rabbitmq'))"
        )
        while time.monotonic() < deadline:
            try:
                probe = docker("exec", "-T", "commandes", "python", "-c", health_probe)
                if probe.stdout.strip().endswith("503 down"):
                    command_down = True
                    break
            except (httpx.HTTPError, subprocess.CalledProcessError):
                pass
            time.sleep(1)
        check(command_down, "le healthcheck Commandes n'a pas détecté RabbitMQ arrêté")

        with httpx.Client(base_url=BASE, timeout=20) as client:
            order = client.post(
                "/api/commandes/orders",
                headers=user_headers,
                json={
                    "items": [{"product_id": product["id"], "quantity": 1}],
                    "delivery_address": "Test reprise, Adjamé",
                    "delivery_phone": "0707070707",
                },
            )
            order.raise_for_status()
            order_id = int(order.json()["id"])

        pending_check = (
            "from app.database import SessionLocal; from app.models import OutboxEvent; "
            "from sqlalchemy import select; import sys; s=SessionLocal(); "
            "r=s.scalar(select(OutboxEvent).where(OutboxEvent.payload['order_id'].as_integer()==int(sys.argv[1]))); "
            "print(bool(r is not None and r.published_at is None)); s.close()"
        )
        pending = docker("exec", "-T", "commandes", "python", "-c", pending_check, str(order_id))
        check(pending.stdout.strip().endswith("True"), "l'événement n'est pas resté en attente dans l'outbox")
        print(f"[OK] commande {order_id} créée avec RabbitMQ arrêté; événement conservé dans l'outbox")
    finally:
        docker("start", "rabbitmq")

    deadline = time.monotonic() + 90
    notified = False
    while time.monotonic() < deadline:
        try:
            health = httpx.get(f"{BASE}/api/notifications/health", timeout=5)
            if health.status_code == 200:
                response = httpx.get(
                    f"{BASE}/api/notifications/notifications?page_size=100",
                    headers=admin_headers,
                    timeout=5,
                )
                if response.status_code == 200 and any(
                    item["order_id"] == order_id for item in response.json()["items"]
                ):
                    notified = True
                    break
        except httpx.HTTPError:
            pass
        time.sleep(2)
    check(notified, "aucune notification après le retour de RabbitMQ")

    published_check = pending_check.replace("r.published_at is None", "r.published_at is not None")
    published = docker("exec", "-T", "commandes", "python", "-c", published_check, str(order_id))
    check(published.stdout.strip().endswith("True"), "l'événement outbox n'est pas marqué publié")
    print("[OK] RabbitMQ rétabli; l'outbox a publié l'événement et Notifications l'a persisté")


if __name__ == "__main__":
    main()
