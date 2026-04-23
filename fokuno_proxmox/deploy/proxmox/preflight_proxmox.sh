#!/usr/bin/env sh
set -eu

# Preflight-Check vor erstem Proxmox-Go-Live.
# Aufruf im Ordner deploy/proxmox:
#   chmod +x preflight_proxmox.sh
#   ./preflight_proxmox.sh

if [ ! -f ".env" ]; then
  echo "Fehler: .env fehlt. Bitte aus .env.example erzeugen." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

require_var() {
  name="$1"
  val="${2:-}"
  if [ -z "${val}" ]; then
    echo "Fehler: ${name} ist leer." >&2
    exit 1
  fi
}

require_var "STAGING_DOMAIN" "${STAGING_DOMAIN:-}"
require_var "TLS_EMAIL" "${TLS_EMAIL:-}"
require_var "POSTGRES_USER" "${POSTGRES_USER:-}"
require_var "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"
require_var "POSTGRES_DB" "${POSTGRES_DB:-}"
require_var "API_TOKEN_SECRET" "${API_TOKEN_SECRET:-}"
require_var "ADMIN_EMAIL" "${ADMIN_EMAIL:-}"

echo "[1/6] Docker/Compose verfügbar..."
docker version >/dev/null
docker compose version >/dev/null

echo "[2/6] Compose-Datei validieren..."
docker compose --env-file .env -f staging-compose.proxmox.yml config -q

echo "[3/6] Domain-Auflösung prüfen..."
if command -v getent >/dev/null 2>&1; then
  getent hosts "${STAGING_DOMAIN}" >/dev/null || {
    echo "Warnung: ${STAGING_DOMAIN} löst lokal nicht auf."
  }
else
  echo "Hinweis: getent nicht verfügbar, DNS-Prüfung übersprungen."
fi

echo "[4/6] Secrets-Minimallänge prüfen..."
[ "${#POSTGRES_PASSWORD}" -ge 16 ] || echo "Warnung: POSTGRES_PASSWORD < 16 Zeichen."
[ "${#API_TOKEN_SECRET}" -ge 32 ] || echo "Warnung: API_TOKEN_SECRET < 32 Zeichen."

echo "[5/6] Ports (80/443) lokal prüfen..."
if command -v ss >/dev/null 2>&1; then
  ss -ltn | grep -E ':(80|443)\s' >/dev/null || {
    echo "Hinweis: 80/443 lauschen aktuell noch nicht (vor Start normal)."
  }
else
  echo "Hinweis: ss nicht verfügbar, Port-Check übersprungen."
fi

echo "[6/6] Ergebnis"
echo "Preflight abgeschlossen. Du kannst jetzt deploy_update.sh ausführen."
