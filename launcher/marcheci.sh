#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"
ACTION="${1:-start}"
SERVICE="${2:-}"
CORE_COMPOSE="compose.yaml"
MONITOR_COMPOSE="monitoring/zabbix/compose.yaml"
SECRET_FILES="postgres_owner_password.secret catalogue_db_password.secret commandes_db_password.secret utilisateurs_db_password.secret notifications_db_password.secret catalogue_database_url.secret commandes_database_url.secret utilisateurs_database_url.secret notifications_database_url.secret jwt_secret.secret rabbitmq_password.secret svc_commandes_password.secret admin_password.secret zabbix_db_password.secret"

fail() { printf '\n[ERREUR] %s\n' "$1" >&2; exit 1; }
ok() { printf '[OK] %s\n' "$1"; }

python_cmd() {
  if [ -x "$ROOT/.venv/bin/python" ]; then printf '%s' "$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then command -v python3
  elif command -v python >/dev/null 2>&1; then command -v python
  else return 1
  fi
}

check_docker() {
  command -v docker >/dev/null 2>&1 || fail 'Docker CLI est introuvable. Installez Docker Desktop ou Docker Engine, puis relancez launcher/start.sh.'
  docker info --format '{{.ServerVersion}}' >/dev/null 2>&1 || fail 'Le moteur Docker ne répond pas. Démarrez Docker Desktop (ou le service Docker), attendez qu’il soit prêt, puis relancez launcher/start.sh.'
  docker compose version >/dev/null 2>&1 || fail 'Docker Compose v2 est indisponible. Mettez Docker Desktop ou le plugin Compose à jour.'
  ok 'Docker et Docker Compose sont opérationnels.'
}

check_config() {
  if [ ! -f .env ]; then
    cp .env.example .env
    fail 'Le modèle .env vient d’être créé. Ouvrez .env, remplacez les valeurs CHANGE_ME par des secrets, enregistrez, puis relancez launcher/start.sh.'
  fi
  py="$(python_cmd)" || fail 'Python 3.12+ est requis pour vérifier la configuration et préparer les secrets. Installez-le puis relancez le script.'
  "$py" scripts/sync_secrets.py --check || fail 'Configuration .env incomplète. Corrigez les valeurs indiquées, puis relancez le script.'
  for name in $SECRET_FILES; do
    if [ ! -s "secrets/$name" ]; then
      "$py" scripts/sync_secrets.py --missing-only || fail 'Impossible de préparer les fichiers secrets depuis .env.'
      break
    fi
  done
  for name in $SECRET_FILES; do [ -s "secrets/$name" ] || fail "Fichier secret manquant : secrets/$name"; done
  [ -f "$CORE_COMPOSE" ] && [ -f gateway/nginx.conf ] || fail 'Fichiers du projet manquants. Vérifiez que le dépôt MarchéCI est complet.'
  ok 'Configuration, fichiers secrets et Compose vérifiés.'
}

gateway_port() {
  port="$(awk -F= '$1=="GATEWAY_PORT" {gsub(/[[:space:]]/,"",$2); print $2; exit}' .env)"
  printf '%s' "${port:-80}"
}

test_url() {
  curl --fail --silent --show-error --max-time 4 "$1" >/dev/null 2>&1
}

wait_url() {
  url="$1"
  tries="${2:-30}"
  i=0
  while [ "$i" -lt "$tries" ]; do
    test_url "$url" && return 0
    i=$((i + 1))
    sleep 2
  done
  return 1
}

start_app() {
  printf 'MARCHÉCI — DÉMARRAGE\n\n'
  if [ ! -f .env ]; then check_config; fi
  check_docker
  check_config
  docker compose -f "$CORE_COMPOSE" config --quiet || fail 'La configuration Docker Compose est invalide. Vérifiez .env et les fichiers du projet.'
  ok 'Configuration Docker validée. Construction et démarrage des services…'
  if ! docker compose -f "$CORE_COMPOSE" up -d --build --wait --wait-timeout 240; then
    printf '\n[ERREUR] Au moins un service n’a pas démarré. État actuel :\n' >&2
    docker compose -f "$CORE_COMPOSE" ps || true
    printf 'Consultez les journaux avec launcher/logs.sh.\n' >&2
    exit 1
  fi
  port="$(gateway_port)"
  base="http://localhost:$port"
  all_healthy=1
  for item in 'Catalogue:/api/catalogue/health' 'Commandes:/api/commandes/health' 'Utilisateurs:/api/utilisateurs/health' 'Notifications:/api/notifications/health'; do
    name="${item%%:*}"
    path="${item#*:}"
    if wait_url "$base$path" 30; then ok "$name opérationnel."; else printf '[ÉCHEC] %s ne répond pas (%s).\n' "$name" "$path"; all_healthy=0; fi
  done
  if wait_url "$base/" 30; then ok 'Frontend accessible.'; else printf '[ÉCHEC] Frontend inaccessible.\n'; all_healthy=0; fi
  [ "$all_healthy" -eq 1 ] || fail 'Un contrôle HTTP a échoué. Utilisez launcher/status.sh et launcher/logs.sh pour le diagnostic.'
  printf '\nBoutique : %s/\nAPI :      %s/api/\nDocs API : %s/docs/catalogue/\n' "$base" "$base" "$base"
  printf 'Supervision : lancez launcher/monitoring.sh (facultatif, port 8090).\n'
  printf 'STATUT : APPLICATION DÉMARRÉE\n'
}

case "$ACTION" in
  start) start_app ;;
  stop)
    check_docker
    monitor_ids="$(docker compose -f "$MONITOR_COMPOSE" ps -q zabbix-web 2>/dev/null || true)"
    if [ -n "$monitor_ids" ]; then docker compose -f "$MONITOR_COMPOSE" down || fail 'Arrêt de la supervision incomplet.'; fi
    docker compose -f "$CORE_COMPOSE" down || fail 'Arrêt de MarchéCI incomplet.'
    ok 'MarchéCI arrêté. Les volumes de données ont été conservés.'
    ;;
  status)
    check_docker
    docker compose -f "$CORE_COMPOSE" ps
    port="$(gateway_port)"
    for item in 'Catalogue:/api/catalogue/health' 'Commandes:/api/commandes/health' 'Utilisateurs:/api/utilisateurs/health' 'Notifications:/api/notifications/health'; do
      name="${item%%:*}"; path="${item#*:}"
      if test_url "http://localhost:$port$path"; then ok "$name opérationnel."; else printf '[INDISPONIBLE] %s\n' "$name"; fi
    done
    monitor_ids="$(docker compose -f "$MONITOR_COMPOSE" ps -q zabbix-web 2>/dev/null || true)"
    if [ -n "$monitor_ids" ]; then
      monitor_port="$(awk -F= '$1=="MON_WEB_PORT" {gsub(/[[:space:]]/,"",$2); print $2; exit}' .env)"
      monitor_bind="$(awk -F= '$1=="MON_WEB_BIND" {gsub(/[[:space:]]/,"",$2); print $2; exit}' .env)"
      printf 'Supervision : http://%s:%s/\n' "${monitor_bind:-127.0.0.1}" "${monitor_port:-8090}"
    fi
    ;;
  logs)
    check_docker
    case "$SERVICE" in
      zabbix-*) docker compose -f "$MONITOR_COMPOSE" logs --tail=100 "$SERVICE" ;;
      '') docker compose -f "$CORE_COMPOSE" logs --tail=100 ;;
      *) docker compose -f "$CORE_COMPOSE" logs --tail=100 "$SERVICE" ;;
    esac
    ;;
  monitoring)
    check_docker
    check_config
    zabbix_password="$(awk -F= '$1=="ZABBIX_ADMIN_PASSWORD" {sub(/^[[:space:]]*/,"",$2); sub(/[[:space:]]*$/, "", $2); print $2; exit}' .env)"
    case "$zabbix_password" in CHANGE_ME*) fail 'Configurez ZABBIX_ADMIN_PASSWORD avec un secret privé dans .env.' ;; esac
    [ "${#zabbix_password}" -ge 12 ] || fail 'ZABBIX_ADMIN_PASSWORD doit compter au moins 12 caractères.'
    gateway_ids="$(docker compose -f "$CORE_COMPOSE" ps -q gateway)"
    [ -n "$gateway_ids" ] || fail 'Démarrez MarchéCI avec launcher/start.sh avant la supervision.'
    docker compose -f "$MONITOR_COMPOSE" config --quiet || fail 'Configuration Zabbix invalide.'
    docker compose -f "$MONITOR_COMPOSE" up -d --wait --wait-timeout 180 || fail 'La pile Zabbix ne démarre pas. Consultez launcher/logs.sh zabbix-web.'
    py="$(python_cmd)" || fail 'Python 3.12+ est nécessaire pour configurer les sondes Zabbix.'
    monitor_host="$(awk -F= '$1=="MON_WEB_BIND" {gsub(/[[:space:]]/,"",$2); print $2; exit}' .env)"
    monitor_host="${monitor_host:-127.0.0.1}"
    case "$monitor_host" in 0.0.0.0|::) monitor_host=127.0.0.1 ;; esac
    monitor_port="$(awk -F= '$1=="MON_WEB_PORT" {gsub(/[[:space:]]/,"",$2); print $2; exit}' .env)"
    monitor_port="${monitor_port:-8090}"
    ZABBIX_API_HOST="$monitor_host" ZABBIX_API_PORT="$monitor_port" "$py" monitoring/zabbix/configure_zabbix_admin.py || fail 'Impossible de configurer le mot de passe administrateur Zabbix.'
    ZABBIX_API_URL="http://$monitor_host:$monitor_port/api_jsonrpc.php" "$py" monitoring/zabbix/provisioning.py verify || fail 'Le provisionnement ou la collecte Zabbix a échoué. Consultez launcher/logs.sh zabbix-server.'
    monitor_url="http://$monitor_host:$monitor_port/"
    if wait_url "$monitor_url" 30; then ok "Zabbix accessible sur $monitor_url"; else fail 'Zabbix a démarré mais son interface ne répond pas encore.'; fi
    ;;
  *) fail 'Action inconnue. Utilisez start, stop, status, logs ou monitoring.' ;;
esac
