"""Test de fumée Étape 3 : vite dev + 4 microservices réels, proxy /api/* vérifié.

Usage : .venv\\Scripts\\python.exe tests\\smoke_frontend.py
Démarre catalogue(5211), utilisateurs(5212), commandes(5213), notifications(5215)
+ `npm run dev`, puis vérifie via le serveur Vite que :
  1. GET / renvoie bien l'application React (index.html)
  2. GET /api/catalogue/products passe le proxy vers le service catalogue
  3. La connexion (/api/utilisateurs/auth/login) renvoie un JWT
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv" / "scripts" / "python.exe"
NPM = Path("C:/Program Files/nodejs/npm.cmd")

JWT_SECRET = "integration-secret-0123456789abcdef0123456789abcde"
LOG_DIR = Path(tempfile.gettempdir()) / "marcheci_smoke"
LOG_DIR.mkdir(exist_ok=True)

SERVICES = {
    "catalogue": (5211, {"REDIS_ENABLED": "false"}),
    "utilisateurs": (5212, {}),
    "commandes": (5213, {"CATALOGUE_URL": "http://127.0.0.1:5211", "EVENTS_ENABLED": "false"}),
    "notifications": (5215, {"EVENTS_ENABLED": "false"}),
}


def migrate(service: str, db: Path) -> None:
    subprocess.run(
        [str(VENV_PY), "-m", "alembic", "upgrade", "head"],
        cwd=str(ROOT / "services" / service),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db}", "JWT_SECRET": JWT_SECRET},
        check=True, capture_output=True, timeout=120,
    )


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="marcheci_smoke_db_"))
    procs: list[subprocess.Popen] = []
    files: list = []

    def spawn(cmd: list[str], cwd: Path, env: dict, name: str) -> subprocess.Popen:
        f = (LOG_DIR / f"{name}.log").open("w", encoding="utf-8")
        files.append(f)
        p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=f, stderr=subprocess.STDOUT)
        procs.append(p)
        return p

    try:
        env_base = {**os.environ, "JWT_SECRET": JWT_SECRET, "JWT_ISSUER": "marcheci", "JWT_AUDIENCE": "marcheci"}
        for svc, (port, extra) in SERVICES.items():
            db = workdir / f"{svc}.db"
            migrate(svc, db)
            spawn([str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                  ROOT / "services" / svc, {**env_base, "DATABASE_URL": f"sqlite:///{db}", **extra}, svc)

        # attente services
        deadline = time.time() + 60
        for svc, (port, _) in SERVICES.items():
            while time.time() < deadline:
                try:
                    if httpx.get(f"http://127.0.0.1:{port}/health", timeout=8).status_code in (200, 503):
                        break
                except httpx.HTTPError:
                    time.sleep(0.6)
            else:
                print(f"[FAIL] {svc} n'a pas démarré")
                return 1
        print("[OK] 4 microservices up")

        # admin role pour tester une route protégée via proxy
        import sqlite3
        # vite dev
        vite_env = {**os.environ, "BROWSER": "none"}
        spawn([str(NPM), "run", "dev", "--", "--host", "127.0.0.1"], ROOT / "frontend", vite_env, "vite")
        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                if httpx.get("http://127.0.0.1:5173/", timeout=8).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.7)
        else:
            print("[FAIL] vite dev n'a pas démarré")
            return 1
        print("[OK] vite dev up")

        vite = "http://localhost:5173"

        # 1) application React servie
        r = httpx.get(f"{vite}/", timeout=10)
        assert r.status_code == 200 and 'id="root"' in r.text, "index.html React attendu"
        print("[OK] GET / → application React servie")

        # 2) proxy → catalogue public
        r = httpx.get(f"{vite}/api/catalogue/products", timeout=10)
        assert r.status_code == 200, (r.status_code, r.text[:200])
        page = r.json()
        assert {"items", "total", "page"} <= set(page), "objet ProductPage attendu"
        print(f"[OK] proxy /api/catalogue/products → {page['total']} produits exposés")

        # 3) création compte + login via proxy → JWT réel
        email = "smoke@example.ci"
        r = httpx.post(f"{vite}/api/utilisateurs/auth/register",
                       json={"email": email, "password": "Smoke1234", "full_name": "Smoke Test"}, timeout=10)
        assert r.status_code in (201, 409), r.text
        r = httpx.post(f"{vite}/api/utilisateurs/auth/login",
                       json={"email": email, "password": "Smoke1234"}, timeout=10)
        assert r.status_code == 200 and r.json().get("access_token"), r.text
        print("[OK] login via proxy → JWT HS256 émis par utilisateurs")

        print("\nSMOKE FRONTEND : TOUT PASSED ✅")
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        for f in files:
            try:
                f.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
