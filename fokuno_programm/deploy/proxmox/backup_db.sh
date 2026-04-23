#!/usr/bin/env sh
set -eu

# Erstellt einen Postgres-Dump aus dem Staging-Container.
# Aufruf im Ordner deploy/proxmox:
#   chmod +x backup_db.sh
#   ./backup_db.sh

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/ahds-staging-${TS}.sql.gz"

# .env laden (POSTGRES_USER/POSTGRES_DB etc.)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
else
  echo "Fehler: .env nicht gefunden (im Ordner deploy/proxmox ausführen)." >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

docker compose --env-file .env -f staging-compose.proxmox.yml exec -T postgres_staging \
  pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  | gzip -9 > "${OUT}"

echo "Backup geschrieben: ${OUT}"
