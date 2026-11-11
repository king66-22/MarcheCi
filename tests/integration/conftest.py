"""Fixtures d'intégration : chaque service est un VRAI process uvicorn distinct.

RabbitMQ et Redis ne sont pas disponibles localement sans Docker :
REDIS_ENABLED=false et EVENTS_ENABLED=false pour tous les services — le test
d'intégration couvre la communication HTTP réelle entre services.
"""

import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
SERVICES = ROOT / "services"

PORT_CATALOGUE = 5211
PORT_UTILISATEURS = 5212
PORT_COMMANDES = 5213
PORT_COMMANDES_BROKEN_CAT = 5214
PORT_NOTIFICATIONS = 5215
PORT_DEAD = 52198  # port fermé livré au test de dégradation

JWT_SECRET = "integration-secret-0123456789abcdef0123456789abcde"

DEFAULT_ENV = {
    "REDIS_ENABLED": "false",
    "EVENTS_ENABLED": "false",
    "JWT_SECRET": JWT_SECRET,
    "JWT_ISSUER": "marcheci",
    "JWT_AUDIENCE": "marcheci",
}

ACCOUNTS = {
    "admin": ("admin@example.ci", "AdminFort123"),
    "client": ("client@example.ci", "Client1234"),
    "svc": ("svc.commandes@example.ci", "SysCmd123!"),
}


def base_env(db_path: Path) -> dict:
    env = {**os.environ, **DEFAULT_ENV, "DATABASE_URL": f"sqlite:///{db_path}"}
    return env


def start_service(service: str, port: int, env: dict, log_dir: Path) -> subprocess.Popen:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / f"{service}-{port}.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            str(VENV_PY), "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=str(SERVICES / service),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    proc._log_file = log_file  # noqa: SLF001 (stockage interne fixture)
    return proc


def wait_ready(url: str, proc: subprocess.Popen, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Process {url} exit précoce — lire les logs")
        try:
            resp = httpx.get(url, timeout=10)
            if resp.status_code in (200, 503):
                return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise TimeoutError(f"{url} n'a pas démarré en {timeout}s")


def migrate(service: str, db_path: Path) -> None:
    subprocess.run(
        [str(VENV_PY), "-m", "alembic", "upgrade", "head"],
        cwd=str(SERVICES / service),
        env=base_env(db_path),
        check=True,
        capture_output=True,
        timeout=120,
    )


def set_admin_role(db_path: Path, emails: list[str]) -> None:
    conn = sqlite3.connect(db_path, timeout=15)
    try:
        for email in emails:
            conn.execute("UPDATE users SET role='ADMIN' WHERE email=?", (email,))
        conn.commit()
    finally:
        conn.close()


def is_port_closed(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return False
        except (ConnectionRefusedError, OSError):
            return True


@pytest.fixture(scope="session")
def stack(tmp_path_factory):
    """Démarre 4 services réels + 1 instance commandes avec un catalogue mort."""
    workdir = tmp_path_factory.mktemp("marcheci_itg")
    logs = workdir / "logs"
    dbs = {name: workdir / f"{name}.db" for name in ("catalogue", "utilisateurs", "commandes", "notifications", "commandes2", "notifications")}

    procs: list[subprocess.Popen] = []

    def stop_all():
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        for p in procs:
            try:
                p._log_file.close()  # noqa: SLF001
            except Exception:
                pass

    try:
        # Migrations (une base par service, exigence « une base par microservice »)
        for svc, db_name in (("catalogue", "catalogue"), ("utilisateurs", "utilisateurs"),
                             ("commandes", "commandes"), ("commandes", "commandes2"),
                             ("notifications", "notifications")):
            migrate(svc, dbs[db_name])

        # --- Services principaux
        procs.append(start_service("catalogue", PORT_CATALOGUE, base_env(dbs["catalogue"]), logs))
        procs.append(start_service("utilisateurs", PORT_UTILISATEURS, base_env(dbs["utilisateurs"]), logs))
        procs.append(start_service(
            "commandes", PORT_COMMANDES,
            {
                **base_env(dbs["commandes"]),
                "CATALOGUE_URL": f"http://127.0.0.1:{PORT_CATALOGUE}",
                "UTILISATEURS_URL": f"http://127.0.0.1:{PORT_UTILISATEURS}",
                "SVC_COMMANDES_EMAIL": ACCOUNTS["svc"][0],
                "SVC_COMMANDES_PASSWORD": ACCOUNTS["svc"][1],
            },
            logs,
        ))
        procs.append(start_service("notifications", PORT_NOTIFICATIONS, base_env(dbs["notifications"]), logs))

        wait_ready(f"http://127.0.0.1:{PORT_CATALOGUE}/health", procs[0])
        wait_ready(f"http://127.0.0.1:{PORT_UTILISATEURS}/health", procs[1])
        wait_ready(f"http://127.0.0.1:{PORT_COMMANDES}/health", procs[2])
        wait_ready(f"http://127.0.0.1:{PORT_NOTIFICATIONS}/health", procs[3])

        # Création des comptes via l'API ; role ADMIN ensuite en DB
        u = f"http://127.0.0.1:{PORT_UTILISATEURS}"
        for email, pwd in ACCOUNTS.values():
            r = httpx.post(f"{u}/auth/register", json={"email": email, "password": pwd, "full_name": "Intégration"}, timeout=10)
            assert r.status_code in (201, 409), r.text
        set_admin_role(dbs["utilisateurs"], [ACCOUNTS["admin"][0], ACCOUNTS["svc"][0]])

        # --- Instance commandes avec catalogue injoignable (port mort vérifié)
        assert is_port_closed(PORT_DEAD), "le port de test du faux catalogue doit être fermé"
        procs.append(start_service(
            "commandes", PORT_COMMANDES_BROKEN_CAT,
            {
                **base_env(dbs["commandes2"]),
                "CATALOGUE_URL": f"http://127.0.0.1:{PORT_DEAD}",
                "UTILISATEURS_URL": f"http://127.0.0.1:{PORT_UTILISATEURS}",
                "SVC_COMMANDES_EMAIL": ACCOUNTS["svc"][0],
                "SVC_COMMANDES_PASSWORD": ACCOUNTS["svc"][1],
            },
            logs,
        ))
        wait_ready(f"http://127.0.0.1:{PORT_COMMANDES_BROKEN_CAT}/health", procs[4])

        yield {
            "catalogue": f"http://127.0.0.1:{PORT_CATALOGUE}",
            "utilisateurs": f"http://127.0.0.1:{PORT_UTILISATEURS}",
            "commandes": f"http://127.0.0.1:{PORT_COMMANDES}",
            "commandes_broken": f"http://127.0.0.1:{PORT_COMMANDES_BROKEN_CAT}",
            "notifications": f"http://127.0.0.1:{PORT_NOTIFICATIONS}",
            "dbs": dbs,
        }
    finally:
        stop_all()


@pytest.fixture(scope="session")
def auth_tokens(stack):
    """Jetons réels émis par le service utilisateurs."""
    tokens = {}
    u = stack["utilisateurs"]
    for name, (email, pwd) in ACCOUNTS.items():
        if name == "svc":
            continue  # jeton interne géré par le service commandes
        r = httpx.post(f"{u}/auth/login", json={"email": email, "password": pwd}, timeout=10)
        assert r.status_code == 200, r.text
        tokens[name] = r.json()["access_token"]
    return tokens


def h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
