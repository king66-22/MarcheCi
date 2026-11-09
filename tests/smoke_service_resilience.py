"""Arrête Commandes dans marcheci-e2e et vérifie que Catalogue reste disponible."""

from pathlib import Path
import subprocess
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "marcheci-e2e"
BASE = "http://localhost:8181"


def docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT, *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )


def main() -> None:
    docker("stop", "commandes")
    try:
        with httpx.Client(base_url=BASE, timeout=10) as client:
            catalogue = client.get("/api/catalogue/health")
            if catalogue.status_code != 200:
                raise RuntimeError(f"Catalogue indisponible pendant l'arrêt Commandes: {catalogue.status_code}")
            commandes = client.get("/api/commandes/health")
            if commandes.status_code not in (502, 503) or not commandes.headers.get("content-type", "").startswith("application/json"):
                raise RuntimeError(
                    f"réponse de panne Commandes inattendue: {commandes.status_code} {commandes.text[:160]}"
                )
            print("[OK] Catalogue reste disponible; gateway renvoie une erreur JSON propre pour Commandes arrêté")
    finally:
        docker("start", "commandes")

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{BASE}/api/commandes/health", timeout=5)
            if response.status_code == 200:
                print("[OK] Commandes est rétabli et healthy")
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("Commandes n'a pas retrouvé son état sain après redémarrage")


if __name__ == "__main__":
    main()
