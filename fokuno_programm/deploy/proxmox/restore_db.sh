#!/usr/bin/env sh
set -eu

# Spielt ein .sql.gz-Backup in die Staging-Datenbank ein.
# WARNUNG: Bestehende Daten werden überschrieben.
#
# Aufruf:
#   chmod +x restore_db.sh
#   ./restore_db.sh ./backups/ahds-staging-YYYYmmdd-HHMMSS.sql.gz

if [ "$#" -ne 1 ]; then
  echo "Nutzung: ./restore_db.sh <backup.sql.gz>" >&2
  exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "${BACKUP_FILE}" ]; then
  echo "Fehler: Backup-Datei nicht gefunden: ${BACKUP_FILE}" >&2
  exit 1
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
else
  echo "Fehler: .env nicht gefunden (im Ordner deploy/proxmox ausführen)." >&2
  exit 1
fi

echo "Achtung: Datenbank ${POSTGRES_DB} wird durch ${BACKUP_FILE} ersetzt."
echo "Zum Fortfahren 'yes' eingeben:"
read -r confirm
if [ "${confirm}" != "yes" ]; then
  echo "Abgebrochen."
  exit 1
fi

docker compose --env-file .env -f staging-compose.proxmox.yml exec -T postgres_staging \
  psql -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
docker compose --env-file .env -f staging-compose.proxmox.yml exec -T postgres_staging \
  psql -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB};"

gzip -dc "${BACKUP_FILE}" | docker compose --env-file .env -f staging-compose.proxmox.yml exec -T postgres_staging \
  psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "Restore abgeschlossen: ${BACKUP_FILE}"
