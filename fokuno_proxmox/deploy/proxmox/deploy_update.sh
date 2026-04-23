#!/usr/bin/env sh
set -eu

# Reproduzierbares Update des Staging-Stacks auf Proxmox.
# Aufruf im Ordner deploy/proxmox:
#   chmod +x deploy_update.sh
#   ./deploy_update.sh
#
# Optional:
#   SKIP_BUILD=1 ./deploy_update.sh

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
else
  echo "Fehler: .env nicht gefunden (im Ordner deploy/proxmox ausführen)." >&2
  exit 1
fi

COMPOSE_ARGS="--env-file .env -f staging-compose.proxmox.yml"

echo "[1/4] Pull versuchter Basis-Images..."
docker compose ${COMPOSE_ARGS} pull || true

if [ "${SKIP_BUILD:-0}" = "1" ]; then
  echo "[2/4] Build übersprungen (SKIP_BUILD=1)."
else
  echo "[2/4] Lokale Images bauen..."
  docker compose ${COMPOSE_ARGS} build
fi

echo "[3/4] Stack aktualisieren..."
docker compose ${COMPOSE_ARGS} up -d --remove-orphans

echo "[4/4] Container-Status:"
docker compose ${COMPOSE_ARGS} ps

echo "Update abgeschlossen."
