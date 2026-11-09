"""Set a private Zabbix Admin password on a fresh local monitoring database."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        raise SystemExit("Fichier .env absent.")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def api_url(values: dict[str, str]) -> str:
    host = os.environ.get("ZABBIX_API_HOST", "127.0.0.1")
    port = os.environ.get("ZABBIX_API_PORT", values.get("MON_WEB_PORT", "8090"))
    return f"http://{host}:{port}/api_jsonrpc.php"


class ZabbixApi:
    def __init__(self, url: str):
        self.url = url
        self.request_id = 0

    def call(self, method: str, params: dict, auth: str | None = None) -> object:
        self.request_id += 1
        payload: dict[str, object] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self.request_id,
        }
        if auth:
            payload["auth"] = auth
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json-rpc"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("API Zabbix temporairement indisponible") from exc
        if "error" in result:
            raise RuntimeError(str(result["error"].get("message", "Erreur API Zabbix")))
        return result["result"]

    def wait_ready(self, seconds: int = 300) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                self.call("apiinfo.version", {})
                return
            except RuntimeError:
                time.sleep(5)
        raise SystemExit("L’API Zabbix n’est pas devenue disponible après 5 minutes.")

    def login(self, username: str, password: str) -> dict:
        result = self.call(
            "user.login",
            {"username": username, "password": password, "userData": True},
        )
        if not isinstance(result, dict) or not result.get("sessionid") or not result.get("userid"):
            raise RuntimeError("Réponse de connexion Zabbix incomplète")
        return result


def main() -> None:
    values = read_env()
    username = values.get("ZABBIX_ADMIN_USER", "Admin")
    password = values.get("ZABBIX_ADMIN_PASSWORD", "")
    if username != "Admin":
        raise SystemExit("Le launcher configure le compte initial Admin; gardez ZABBIX_ADMIN_USER=Admin.")
    if not password or password.startswith("CHANGE_ME") or len(password) < 12:
        raise SystemExit("ZABBIX_ADMIN_PASSWORD doit être un secret privé d’au moins 12 caractères dans .env.")

    api = ZabbixApi(api_url(values))
    api.wait_ready()

    try:
        api.login(username, password)
        print("[OK] Mot de passe administrateur Zabbix déjà configuré.")
        return
    except RuntimeError:
        pass

    try:
        initial = api.login("Admin", "zabbix")
    except RuntimeError as exc:
        raise SystemExit(
            "Connexion Zabbix refusée avec le secret de .env et avec le mot de passe initial. "
            "Vérifiez ZABBIX_ADMIN_PASSWORD ou le volume Zabbix existant."
        ) from exc

    api.call(
        "user.update",
        {
            "userid": initial["userid"],
            "passwd": password,
            "current_passwd": "zabbix",
        },
        auth=initial["sessionid"],
    )
    api.login(username, password)
    print("[OK] Mot de passe initial Zabbix remplacé par le secret privé de .env.")


if __name__ == "__main__":
    main()
