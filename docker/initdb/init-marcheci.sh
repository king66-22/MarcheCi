#!/bin/bash
# Création des 4 bases logiques MarchéCI sur LE serveur PostgreSQL unique.
# Exécuté automatiquement par l'image officielle postgres (docker-entrypoint-initdb.d)
# au premier démarrage du volume. Chaque service a SON utilisateur + SA base :
# aucune base partagée (exigence microservices).
set -euo pipefail

: "${POSTGRES_OWNER_USER:?POSTGRES_OWNER_USER doit être défini}"
: "${PGCAT_USER:?} ${PGCAT_PASSWORD_FILE:?} ${PGCAT_DB:?}"
: "${PGCMD_USER:?} ${PGCMD_PASSWORD_FILE:?} ${PGCMD_DB:?}"
: "${PGUSR_USER:?} ${PGUSR_PASSWORD_FILE:?} ${PGUSR_DB:?}"
: "${PGNTF_USER:?} ${PGNTF_PASSWORD_FILE:?} ${PGNTF_DB:?}"

create_database() {
    local db="$1" user="$2" password_file="$3"
    local pass
    pass="$(tr -d '\r\n' < "$password_file")"
    if [[ -z "$pass" ]]; then
        echo "Mot de passe vide pour le rôle ${user}" >&2
        return 1
    fi

    if ! psql -U "$POSTGRES_OWNER_USER" -v ON_ERROR_STOP=1 -v role_name="$user" -d postgres \
        -tAc "SELECT 1 FROM pg_roles WHERE rolname=:'role_name'" | grep -q 1; then
        psql -U "$POSTGRES_OWNER_USER" -v ON_ERROR_STOP=1 \
            -v role_name="$user" -v role_password="$pass" -d postgres <<'SQL'
CREATE ROLE :"role_name" LOGIN PASSWORD :'role_password';
SQL
    fi

    if ! psql -U "$POSTGRES_OWNER_USER" -v ON_ERROR_STOP=1 -v database_name="$db" -d postgres \
        -tAc "SELECT 1 FROM pg_database WHERE datname=:'database_name'" | grep -q 1; then
        psql -U "$POSTGRES_OWNER_USER" -v ON_ERROR_STOP=1 \
            -v database_name="$db" -v role_name="$user" -d postgres <<'SQL'
CREATE DATABASE :"database_name" OWNER :"role_name";
SQL
        psql -U "$POSTGRES_OWNER_USER" -v ON_ERROR_STOP=1 -v database_name="$db" -d postgres <<'SQL'
REVOKE ALL ON DATABASE :"database_name" FROM PUBLIC;
SQL
    fi

    echo ">>> base ${db} prête (owner ${user})"
}

create_database "$PGCAT_DB" "$PGCAT_USER" "$PGCAT_PASSWORD_FILE"
create_database "$PGCMD_DB" "$PGCMD_USER" "$PGCMD_PASSWORD_FILE"
create_database "$PGUSR_DB" "$PGUSR_USER" "$PGUSR_PASSWORD_FILE"
create_database "$PGNTF_DB" "$PGNTF_USER" "$PGNTF_PASSWORD_FILE"

echo ">>> 4 bases logiques créées — une par microservice"
