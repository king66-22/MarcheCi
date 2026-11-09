"""Create ignored Docker secret files from the local .env configuration."""

import argparse
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
SECRET_DIR = ROOT / "secrets"


def read_env() -> dict[str, str]:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        raise SystemExit("Fichier .env absent; copiez d'abord .env.example et renseignez les secrets.")
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "")
    if not value or value.startswith("CHANGE_ME"):
        raise SystemExit(f"{key} doit être remplacé par un secret fort dans .env.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="create absent files without overwriting existing secret files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate required core settings without writing secret files",
    )
    args = parser.parse_args()
    values = read_env()
    secrets: dict[str, str] = {
        "postgres_owner_password.secret": required(values, "POSTGRES_OWNER_PASSWORD"),
        "catalogue_db_password.secret": required(values, "PGCAT_PASSWORD"),
        "commandes_db_password.secret": required(values, "PGCMD_PASSWORD"),
        "utilisateurs_db_password.secret": required(values, "PGUSR_PASSWORD"),
        "notifications_db_password.secret": required(values, "PGNTF_PASSWORD"),
        "jwt_secret.secret": required(values, "JWT_SECRET"),
        "rabbitmq_password.secret": required(values, "RABBITMQ_PASSWORD"),
        "svc_commandes_password.secret": required(values, "SVC_COMMANDES_PASSWORD"),
        "admin_password.secret": required(values, "ADMIN_PASSWORD"),
        "zabbix_db_password.secret": required(values, "MON_ZBX_DB_PASSWORD"),
    }
    required(values, "POSTGRES_OWNER_USER")
    required(values, "RABBITMQ_USER")
    required(values, "JWT_ISSUER")
    required(values, "SVC_COMMANDES_EMAIL")
    required(values, "ADMIN_EMAIL")
    if len(secrets["jwt_secret.secret"].encode("utf-8")) < 32:
        raise SystemExit("JWT_SECRET doit contenir au moins 32 octets.")
    gateway_port = values.get("GATEWAY_PORT", "80")
    if not gateway_port.isdecimal() or not 1 <= int(gateway_port) <= 65535:
        raise SystemExit("GATEWAY_PORT doit être un port TCP entre 1 et 65535.")
    for service, prefix in (
        ("catalogue", "PGCAT"),
        ("commandes", "PGCMD"),
        ("utilisateurs", "PGUSR"),
        ("notifications", "PGNTF"),
    ):
        user = required(values, f"{prefix}_USER")
        password = required(values, f"{prefix}_PASSWORD")
        database = required(values, f"{prefix}_DB")
        secrets[f"{service}_database_url.secret"] = (
            f"postgresql+psycopg2://{quote(user, safe='')}:{quote(password, safe='')}"
            f"@postgres:5432/{quote(database, safe='')}"
        )

    if args.check:
        print("Configuration principale vérifiée (valeurs non affichées).")
        return

    SECRET_DIR.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    for name, secret in secrets.items():
        path = SECRET_DIR / name
        if args.missing_only and path.exists():
            skipped += 1
            continue
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(secret + "\n")
        created += 1
        try:
            path.chmod(0o600)
        except OSError:
            pass  # Docker Desktop Windows ACLs govern access on Windows.
    if args.missing_only:
        print(f"{created} fichier(s) secret(s) créé(s), {skipped} existant(s) préservé(s).")
    else:
        print(f"Créé/mis à jour {created} fichiers secrets ignorés par Git.")


if __name__ == "__main__":
    main()
