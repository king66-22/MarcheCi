"""Provisionnement Zabbix MarchéCI (Étape 6) — tout via l'API JSON-RPC.

1. crée le groupe + hôte "MarchéCI"
2. items HTTP agent (GET) sur les /health des 5 cibles :
      gateway, catalogue, commandes, utilisateurs, notifications
   + item agent2 (agent.ping) pour vérifier l'Agent 2
3. triggers : absence de donnée 63 s = PROBLÈME (service down/503)
4. vérifie la collecte puis (mode "alerte") déclenche l'incident catalogue.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
try:
    import httpx
except ImportError:  # Le provisionnement local reste utilisable sans dépendance Python supplémentaire.
    from urllib import error, request

    class _Response:
        def __init__(self, body: bytes):
            self._body = body

        def json(self):
            return json.loads(self._body.decode("utf-8"))

    class _HttpxCompat:
        HTTPError = error.URLError

        @staticmethod
        def post(url, *, json, timeout=30):
            req = request.Request(
                url,
                data=__import__("json").dumps(json).encode("utf-8"),
                headers={"Content-Type": "application/json-rpc"},
                method="POST",
            )
            with request.urlopen(req, timeout=timeout) as response:
                return _Response(response.read())

    httpx = _HttpxCompat()

API = os.environ.get("ZABBIX_API_URL", "http://localhost:8090/api_jsonrpc.php")
HOST_NAME = "MarcheCI"  # les caractères accentués sont refusés par Zabbix (noms d'hôtes)


def get_admin_credentials() -> tuple[str, str]:
    """Lit les identifiants depuis l'environnement ou .env, sans valeur par défaut."""
    values: dict[str, str] = {}
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    user = os.environ.get("ZABBIX_ADMIN_USER", values.get("ZABBIX_ADMIN_USER", "Admin"))
    password = os.environ.get("ZABBIX_ADMIN_PASSWORD", values.get("ZABBIX_ADMIN_PASSWORD", ""))
    if not password or password.startswith("CHANGE_ME"):
        raise RuntimeError("ZABBIX_ADMIN_PASSWORD doit être configuré dans .env ou l'environnement")
    return user, password

ITEMS = {
    "health.gateway": "http://gateway:8080/health",
    "health.catalogue": "http://catalogue:8000/health",
    "health.commandes": "http://commandes:8000/health",
    "health.utilisateurs": "http://utilisateurs:8000/health",
    "health.notifications": "http://notifications:8000/health",
}


class Zbx:
    def __init__(self) -> None:
        self.auth = None
        self.rid = 0

    def call(self, method: str, params: dict) -> dict:
        self.rid += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": self.rid}
        if self.auth:
            payload["auth"] = self.auth
        r = httpx.post(API, json=payload, timeout=30)
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"{method} -> {data['error']}")
        return data["result"]

    def login(self, user: str, password: str) -> None:
        self.auth = self.call("user.login", {"username": user, "password": password})

    def login_wait(self, user: str, password: str, seconds: int = 300) -> None:
        """La création du schéma DB au premier démarrage prend plusieurs minutes."""
        deadline = time.time() + seconds
        last_err = None
        while time.time() < deadline:
            try:
                self.login(user, password)
                return
            except RuntimeError as exc:
                last_err = exc
            time.sleep(10)
        raise TimeoutError(f"login Zabbix impossible après {seconds}s : {last_err}")


def wait_web(seconds: int = 180) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            r = httpx.post(API, json={"jsonrpc": "2.0", "method": "apiinfo.version", "id": 0}, timeout=10)
            if r.status_code == 200:
                print(f"[OK] API Zabbix joignable ({r.json()})")
                return
        except httpx.HTTPError:
            pass
        time.sleep(3)
    raise TimeoutError("API Zabbix inaccessible")


def provision() -> None:
    z = Zbx()
    wait_web()
    z.login_wait(*get_admin_credentials())
    print("[OK] login Admin")

    params = {"filter": {"name": HOST_NAME}}
    groups = z.call("hostgroup.get", {"filter": {"name": "MarchéCI"}})
    if not groups:
        gid = z.call("hostgroup.create", {"name": "MarchéCI"})["groupids"][0]
        print("[OK] groupe MarchéCI créé")
    else:
        gid = groups[0]["groupid"]

    hosts = z.call("host.get", params)
    if hosts:
        host_id = hosts[0]["hostid"]
        print("[OK] hôte MarchéCI existe déjà")
    else:
        host_id = z.call("host.create", {
            "host": HOST_NAME,
            "groups": [{"groupid": gid}],
            "interfaces": [{
                "type": 1, "main": 1, "useip": 0, "ip": "",
                "dns": "marcheci-monitoring-zabbix-agent2-1", "port": "10050",
            }],
        })["hostids"][0]
        print("[OK] hôte MarchéCI créé (interface Agent 2 : dns marcheci-agent2)")

    # items HTTP agent
    for key, url in ITEMS.items():
        existing = z.call("item.get", {"hostids": host_id, "filter": {"key_": key}})
        if existing:
            if key in ITEMS and existing[0].get("url") != url:
                z.call("item.update", {"itemid": existing[0]["itemid"], "url": url})
                print(f"[OK] item {key} URL mise à jour")
            else:
                print(f"[OK] item {key} existe")
            continue
        z.call("item.create", {
            "hostid": host_id, "name": key, "key_": key, "type": 19,
            "url": url, "request_method": "0", "timeout": "5s",
            "delay": "30s", "value_type": 2,  # 2 = CHAR (corps JSON) ; 3 est "log"
            "history": "7d", "trends": "0",
        })
        print(f"[OK] item {key} -> {url}")

    # item Agent 2 : ping (nécessite l'id de l'interface agent de l'hôte)
    if not z.call("item.get", {"hostids": host_id, "filter": {"key_": "agent.ping"}}):
        itfs = z.call("hostinterface.get", {"hostids": host_id, "filter": {"type": 1}})
        if not itfs:
            print("[WARN] pas d'interface Agent — item agent.ping ignoré")
        else:
            z.call("item.create", {
                "hostid": host_id, "name": "Agent 2 disponible", "key_": "agent.ping",
                "type": 0, "delay": "30s", "value_type": 2, "history": "7d",
                "interfaceid": itfs[0]["interfaceid"],
            })
            print("[OK] item agent.ping (Agent 2)")

    # triggers : pas de donnée depuis 63 s => PROBLÈME (service down / 503 / timeout)
    for key in [*ITEMS, "agent.ping"]:
        trig = f"nodata(/{HOST_NAME}/{key},63s)=1"
        name = f"MarchéCI — {key} injoignable pendant 63 s"
        if z.call("trigger.get", {"hostids": host_id, "filter": {"description": name}}):
            continue
        z.call("trigger.adddependencies" if False else "trigger.create", {
            "description": name,
            "expression": trig,
            "priority": 4,  # High
            "manual_close": 1,
        })
        print(f"[OK] trigger {key}")

    print("\nPROVISIONNEMENT TERMINÉ")


def verify_collect() -> bool:
    z = Zbx()
    z.login_wait(*get_admin_credentials())
    host_id = z.call("host.get", {"filter": {"host": HOST_NAME}})[0]["hostid"]
    item_ids = {i["key_"]: i["itemid"] for i in z.call("item.get", {"hostids": host_id})}
    time.sleep(50)
    ok = True
    for key, _ in item_ids.items():
        item = z.call("item.get", {"hostids": host_id, "filter": {"key_": key}})[0]
        got = item["state"] == "0" and item["lastvalue"] not in ("", "0")
        print(f"[{'OK' if got else 'FAIL'}] {key} état={item['state']} dernière valeur = {str(item['lastvalue'])[:70]}")
        ok = ok and got
    return ok


def demo_alerte() -> None:
    """Arrête les répliques catalogue → PROBLÈME sur health.catalogue -> redémarre."""
    z = Zbx()
    z.login_wait(*get_admin_credentials())
    host_id = z.call("host.get", {"filter": {"host": HOST_NAME}})[0]["hostid"]
    itemid = {i["key_"]: i["itemid"] for i in z.call("item.get", {"hostids": host_id})}["health.catalogue"]

    print(">>> INCIDENT : docker stop des 3 répliques catalogue")
    subprocess.run(["docker", "compose", "stop", "catalogue"], check=True, capture_output=True, timeout=120)
    try:
        deadline = time.time() + 200
        problem = None
        while time.time() < deadline:
            problems = z.call("problem.get", {"objectids": _trigger_id(z, host_id, itemid), "recent": False, "limit": 1})
            if problems:
                problem = problems[0]
                break
            time.sleep(10)
        if problem:
            print(f"[ALERT VUE] {problem['name']} — sévérité {problem['severity']}")
        else:
            print("[FAIL] aucun PROBLÈME apparu en 200 s")
            sys.exit(1)
    finally:
        print(">>> RÉTABLISSEMENT : docker start catalogue")
        subprocess.run(["docker", "compose", "start", "catalogue"], check=True, capture_output=True, timeout=120)
        # résolution automatique au retour des données (< 63 s)
        deadline = time.time() + 150
        while time.time() < deadline:
            if not z.call("problem.get", {"objectids": _trigger_id(z, host_id, itemid), "limit": 1}):
                print("[OK] problème RÉSOLU automatiquement après redémarrage")
                return
            time.sleep(10)
        print("[WARN] problème toujours actif après 150 s (la collecte reprendra au 30 s cycle)")


def _trigger_id(z: Zbx, host_id: str, itemid: str) -> str:
    triggers = z.call("trigger.get", {"hostids": host_id, "itemids": itemid, "limit": 5})
    return triggers[0]["triggerid"]


if __name__ == "__main__":
    mode = (sys.argv[1] if len(sys.argv) > 1 else "tout").lower()
    provision()
    if mode in ("verify", "tout", "provision"):
        if not verify_collect():
            print("[FAIL] collecte incomplète")
            sys.exit(1)
        print("[OK] les 6 items collectent des valeurs")
    if mode == "alerte":
        demo_alerte()
    elif mode == "tout":
        demo_alerte()
    print("\nPHASE 6 TERMINÉE")
