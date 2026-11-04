#!/bin/bash
# Création des 4 bases logiques MarchéCI sur LE serveur PostgreSQL unique.
# Exécuté automatiquement par l'image officielle postgres (docker-entrypoint-initdb.d)
# au premier démarrage du volume. Chaque service a SON utilisateur + SA base :
# aucune base partagée (exigence microservices).
set -euo pipefail

: "${POSTGRES_OWNER_PASSWORD:?POSTGRES_OWNER_PASSWORD doit être défini}"
: "${PGCAT_USER:?} ${PGCAT_PASSWORD:?} ${PGCAT_DB:?}"
: "${PGCMD_USER:?} ${PGCMD_PASSWORD:?} ${PGCMD_DB:?}"
: "${PGUSR_USER:?} ${PGUSR_PASSWORD:?} ${PGUSR_DB:?}"
: "${PGNTF_USER:?} ${PGNTF_PASSWORD:?} ${PGNTF_DB:?}"

create_database() {
    local db="$1" user="$2" pass="$3"

    if ! psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='${user}'" | grep -q 1; then
        psql -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE ${user} LOGIN PASSWORD '${pass}';"
    fi

    if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1; then
        psql -v ON_ERROR_STOP=1 -d postgres -c "CREATE DATABASE ${db} OWNER ${user};"
        psql -v ON_ERROR_STOP=1 -d postgres -c "REVOKE ALL ON DATABASE ${db} FROM PUBLIC;"
    fi

    echo ">>> base ${db} prête (owner ${user})"
}

create_database "$PGCAT_DB" "$PGCAT_USER" "$PGCAT_PASSWORD"
create_database "$PGCMD_DB" "$PGCMD_USER" "$PGCMD_PASSWORD"
create_database "$PGUSR_DB" "$PGUSR_USER" "$PGUSR_PASSWORD"
create_database "$PGNTF_DB" "$PGNTF_USER" "$PGNTF_PASSWORD"

echo ">>> 4 bases logiques créées — une par microservice"
