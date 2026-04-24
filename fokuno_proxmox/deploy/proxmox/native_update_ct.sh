#!/usr/bin/env bash
set -euo pipefail

# AhDs Auto-Update (Host -> CT, ohne Docker)
#
# Ablauf:
# 1) Prüft / aktualisiert /opt/ahds (git pull)
# 2) Kopiert staging_api in den CT
# 3) Installiert Python-Abhängigkeiten im CT
# 4) Startet ahds-staging-api im CT neu
# 5) Prüft /health im CT

CTID="${CTID:-113}"
REPO_DIR="${REPO_DIR:-/opt/ahds}"
BRANCH="${BRANCH:-main}"
APP_DIR_IN_CT="${APP_DIR_IN_CT:-/opt/ahds-native}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Fehlendes Kommando: $1" >&2
    exit 1
  fi
}

need_cmd git
need_cmd pct
need_cmd tar

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "Repo nicht gefunden: ${REPO_DIR}" >&2
  exit 1
fi

API_SRC="${REPO_DIR}/fokuno_proxmox/deploy/staging_api"
if [[ ! -d "${API_SRC}" ]]; then
  echo "API-Quellordner fehlt: ${API_SRC}" >&2
  exit 1
fi

echo "[1/6] Git-Status prüfen..."
if ! pct status "${CTID}" >/dev/null 2>&1; then
  echo "CT ${CTID} nicht gefunden." >&2
  exit 1
fi

echo "[2/6] Repo aktualisieren..."
git -C "${REPO_DIR}" fetch --all --prune
LOCAL_SHA="$(git -C "${REPO_DIR}" rev-parse HEAD)"
REMOTE_SHA="$(git -C "${REPO_DIR}" rev-parse "origin/${BRANCH}")"
if [[ "${LOCAL_SHA}" != "${REMOTE_SHA}" ]]; then
  git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"
else
  echo "Kein neues Git-Update gefunden."
fi

echo "[3/6] API in CT kopieren..."
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT
tar -C "${REPO_DIR}/fokuno_proxmox/deploy" -czf "${WORK_DIR}/staging_api.tar.gz" staging_api
pct push "${CTID}" "${WORK_DIR}/staging_api.tar.gz" /tmp/staging_api.tar.gz
pct exec "${CTID}" -- bash -lc "rm -rf '${APP_DIR_IN_CT}/staging_api' && mkdir -p '${APP_DIR_IN_CT}' && tar -xzf /tmp/staging_api.tar.gz -C '${APP_DIR_IN_CT}' && rm -f /tmp/staging_api.tar.gz"

echo "[4/6] Python-Abhängigkeiten im CT aktualisieren..."
pct exec "${CTID}" -- bash -lc "'${APP_DIR_IN_CT}/venv/bin/pip' install --upgrade pip >/dev/null && '${APP_DIR_IN_CT}/venv/bin/pip' install -r '${APP_DIR_IN_CT}/staging_api/requirements.txt'"

echo "[5/6] Service im CT neu starten..."
pct exec "${CTID}" -- systemctl restart ahds-staging-api

echo "[6/6] Healthcheck..."
pct exec "${CTID}" -- curl -fsS http://127.0.0.1:8000/health
echo
echo "Update erfolgreich für CT ${CTID}."
