"""Orchestrateur Étape 5 : lancement de k6 (image grafana/k6) + chaos.

Exécuter depuis la racine : .venv\\Scripts\\python.exe tests\\load\\orchestrateur.py
 suppose la plateforme docker compose UP (référentiel : la gateway sur le port 80).

Modes :
  python tests/load/orchestrateur.py charge     — comparer 1 vs 3 répliques catalogue
  python tests/load/orchestrateur.py resilience — incident commandes 20 s sous charge
  python tests/load/orchestrateur.py tout       — les deux, à la suite

Résultats : reports/load_1replica.json, reports/load_3replicas.json,
            reports/resilience.json + tableau de synthèse en console.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
TESTS = ROOT / "tests" / "load"

K6_IMAGE = "grafana/k6:1.0.0"
BASE = "http://host.docker.internal"


def run_k6(script: str, out_file: str, env: dict[str, str], timeout: int = 600) -> int:
    cmd = ["docker", "run", "--rm",
           "-v", f"{REPORTS}:/results",
           "-v", f"{TESTS}:/scenarios:ro",
           K6_IMAGE, "run", "--quiet",
           "/scenarios/" + script]
    env_docker = {k: v for k, v in env.items()}
    for key, value in env_docker.items():
        cmd += ["-e", f"{key}={value}"]
    print(">>>", " ".join(cmd[:6]), "…")
    return subprocess.run(cmd, capture_output=False, timeout=timeout).returncode


def scale(replicas: int) -> None:
    print(f"=== scale catalogue={replicas} ===")
    subprocess.run(
        ["docker", "compose", "up", "-d", "--scale", f"catalogue={replicas}"],
        cwd=str(ROOT), check=True, capture_output=True, timeout=300,
    )
    # laisse le check HEALTHCHECK passer + le resolver nginx se rafraîchir (valid=5s)
    time.sleep(8)
    ps = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        cwd=str(ROOT), check=True, capture_output=True, text=True, timeout=60,
    ).stdout
    running = []
    for line in ps.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        arr = t if isinstance(t, list) else [t]
        for c in arr:
            name = c.get("Name") or c.get("Service") or ""
            if name.startswith("marcheci-catalogue-") and (c.get("State") == "running"):
                running.append(name)
    print(f"catalogue: {len(running)} réplique(s) running -> {running}")


def mode_charge() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    common = {"BASE": BASE, "RAMP": "20", "HOLD": "40"}
    for replicas, name in ((1, "load_1replica.json"), (3, "load_3replicas.json")):
        scale(replicas)
        rc = run_k6(
            "load_catalogue.js", name,
            {**common, "VUS": "50", "TAG_RUN": f"replicas={replicas}", "OUT_FILE": name},
        )
        if rc != 0:
            print(f"[FAIL] k6 {name} a échoué (code {rc})")
            sys.exit(1)
        print(f"[OK] {name} généré")

    # synthèse
    rows = []
    for name in ("load_1replica.json", "load_3replicas.json"):
        d = json.loads((REPORTS / name).read_text(encoding="utf-8"))
        print(f"\n--- {name} (tag {d['tag']}) ---")
        print(f"  requêtes totales   : {d['total']['requetes']}  (débit {d['total']['debit_rps']} req/s)")
        print(f"  p95 global         : {d['total']['p95_ms']} ms")
        print(f"  rate de checks     : {d['total']['rate_checks']:.4f}")
        for label, info in (("cache_redis", d["cache_redis"]), ("db_postgres", d["db_postgres"])):
            if info:
                print(f"  {label:<13} : {info['requetes']} reqs, p50 {info['p50_ms']} ms, p95 {info['p95_ms']} ms, max {info['max_ms']} ms")
        print(f"  erreurs            : {d['erreurs']}")
        rows.append((name, d))
    # comparatif
    if len(rows) == 2:
        r1, r3 = rows[0][1], rows[1][1]
        print("\n=== COMPARATIF p95 (ms) 1 réplique -> 3 répliques ===")
        print(f"  cache Redis  : {r1['cache_redis']['p95_ms']} -> {r3['cache_redis']['p95_ms']}")
        print(f"  db Postgres  : {r1['db_postgres']['p95_ms']} -> {r3['db_postgres']['p95_ms']}")
        print(f"  p95 global   : {r1['total']['p95_ms']} -> {r3['total']['p95_ms']}")
        (REPORTS / "comparatif_machines.json").write_text(
            json.dumps({"1replica": r1, "3replicas": r3}, indent=2), encoding="utf-8")


def mode_resilience() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    scale(3)  # scénario d'attaque avec la plateforme "en production"
    subprocess.run(["docker", "compose", "start", "commandes"], cwd=str(ROOT), check=True,
                   capture_output=True, timeout=120)

    # chaos orchestré lors du 2e palier du scénario (t+15 s .. t+35 s)
    script = f"""
    $deadline = (Get-Date).AddSeconds(420)
    $k6 = Start-Process -FilePath docker -ArgumentList 'run','--rm','-v','{REPORTS}:/results','-v','{TESTS}:/scenarios:ro','{K6_IMAGE}','run','--quiet','/scenarios/resilience.js','-e','BASE={BASE}' -PassThru -WindowStyle Hidden -RedirectStandardOutput {REPORTS / 'resilience_k6.log'} -RedirectStandardError {REPORTS / 'resilience_k6.err.log'}
    Start-Sleep -Seconds 15   # régime établi
    docker compose stop commandes   | Out-Null
    Start-Sleep -Seconds 20   # === incident ===
    docker compose start commandes  | Out-Null
    Start-Sleep -Seconds 25   # redémarrage + récupération
    $k6 | Wait-Process -Timeout 90
    """
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, timeout=420)

    data = json.loads((REPORTS / "summary_resilience.json").read_text(encoding="utf-8"))
    cat = data["catalogue"]
    cmd_ = data["commandes"]
    print("\n--- RESILIENCE (incident commandes 20 s sous charge) ---")
    print(f"  catalogue : {cat['requetes']} requêtes, {cat['erreurs']} erreur(s), p95 {cat['p95_ms']} ms")
    print(f"  commandes : {cmd_['ok_200']} ok (200), {cmd_['panne_propre_json']} 502/503 propres, {cmd_['panne_sale']} échec(s) sale(s)")
    (REPORTS / "resilience.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "tout").lower()
    if mode in ("charge", "tout"):
        mode_charge()
    if mode in ("resilience", "tout"):
        mode_resilience()
    print("\nPHASE 5 — ORCHESTRATION TERMINÉE")
