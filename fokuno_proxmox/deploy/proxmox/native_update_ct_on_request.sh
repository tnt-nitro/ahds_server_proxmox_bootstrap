#!/usr/bin/env bash
set -euo pipefail

# Wird auf dem Proxmox-Host per systemd-Timer ausgeführt.
# Liegt im CT die Datei update_request.json (vom Button „Update installieren“),
# wird native_update_ct.sh einmal gestartet.

CTID="${CTID:-113}"
REPO_DIR="${REPO_DIR:-/opt/ahds}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ="/opt/ahds-native/data/update_request.json"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Fehlendes Kommando: $1" >&2
    exit 1
  fi
}

need_cmd pct

if ! pct status "${CTID}" >/dev/null 2>&1; then
  exit 0
fi

if ! pct exec "${CTID}" -- test -f "${REQ}" 2>/dev/null; then
  exit 0
fi

echo "[ahds] Update-Anforderung im CT ${CTID} gefunden, starte native_update_ct.sh ..."
exec env CTID="${CTID}" REPO_DIR="${REPO_DIR}" bash "${SCRIPT_DIR}/native_update_ct.sh"
