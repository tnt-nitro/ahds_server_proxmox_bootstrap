#!/usr/bin/env sh
set -eu

# AhDs Staging One-Command Installer (Proxmox Host).
# Ziel: ähnlich "Helper-Scripts" nutzbar, aber für dieses Repo.
#
# Beispiel (vom PC aus):
# ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_proxmox/deploy/proxmox/install_from_github.sh)\""
#
# Konfigurierbare Variablen:
#   AHDS_REPO_URL      (default: https://github.com/tnt-nitro/fokuno.git)
#   AHDS_REPO_REF      (default: main)
#   AHDS_INSTALL_DIR   (default: /opt/ahds)
#   INSTALL_SYSTEMD    (default: 1)
#   DRY_RUN            (default: 0)
#
# Pflicht (für Erstinstallation ohne bestehende .env):
#   STAGING_DOMAIN, TLS_EMAIL, POSTGRES_PASSWORD, API_TOKEN_SECRET, ADMIN_EMAIL

AHDS_REPO_URL="${AHDS_REPO_URL:-https://github.com/tnt-nitro/fokuno.git}"
AHDS_REPO_REF="${AHDS_REPO_REF:-main}"
AHDS_INSTALL_DIR="${AHDS_INSTALL_DIR:-/opt/ahds}"
INSTALL_SYSTEMD="${INSTALL_SYSTEMD:-1}"
DRY_RUN="${DRY_RUN:-0}"

TARGET_DIR="${AHDS_INSTALL_DIR}/fokuno_proxmox/deploy/proxmox"
REPO_DIR="${AHDS_INSTALL_DIR}"

print_help() {
  cat <<'EOF'
AhDs Proxmox Installer

Nutzung:
  install_from_github.sh [--help] [--dry-run] [--no-systemd]

Optionen:
  --help         Hilfe anzeigen
  --dry-run      Keine Änderungen am System vornehmen
  --no-systemd   Systemd-Setup überspringen

Konfiguration (Env):
  AHDS_REPO_URL, AHDS_REPO_REF, AHDS_INSTALL_DIR
  STAGING_DOMAIN, TLS_EMAIL, POSTGRES_PASSWORD, API_TOKEN_SECRET, ADMIN_EMAIL
  Optional: POSTGRES_USER, POSTGRES_DB, LOGIN_MAX_FEHLVERSUCHE, LOGIN_SPERRE_SEKUNDEN, RESET_TOKEN_TTL_SEKUNDEN

Beispiel:
  STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='***' API_TOKEN_SECRET='***' ADMIN_EMAIL='admin@example.org' ./install_from_github.sh
EOF
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Fehler: benötigtes Kommando fehlt: $1" >&2
    exit 1
  fi
}

run_cmd() {
  if [ "${DRY_RUN}" = "1" ]; then
    echo "[dry-run] $*"
    return 0
  fi
  "$@"
}

set_env_var() {
  file="$1"
  key="$2"
  value="$3"
  if [ -z "${value}" ]; then
    return 0
  fi
  if grep -q "^${key}=" "${file}"; then
    sed -i "s#^${key}=.*#${key}=${value}#g" "${file}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${file}"
  fi
}

prompt_if_missing() {
  key="$1"
  prompt="$2"
  secret="${3:-0}"
  current="$(eval "printf '%s' \"\${$key:-}\"")"
  if [ -n "${current}" ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    return 0
  fi
  if [ "${secret}" = "1" ]; then
    printf "%s: " "${prompt}" >&2
    stty -echo
    IFS= read -r value
    stty echo
    printf "\n" >&2
  else
    printf "%s: " "${prompt}" >&2
    IFS= read -r value
  fi
  eval "$key=\$value"
  export "$key"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --no-systemd)
      INSTALL_SYSTEMD=0
      ;;
    *)
      echo "Unbekannte Option: $1" >&2
      echo "Mit --help anzeigen." >&2
      exit 1
      ;;
  esac
  shift
done

prompt_if_missing "STAGING_DOMAIN" "STAGING_DOMAIN (z. B. staging.example.org)"
prompt_if_missing "TLS_EMAIL" "TLS_EMAIL (Let's Encrypt Kontakt)"
prompt_if_missing "POSTGRES_PASSWORD" "POSTGRES_PASSWORD" "1"
prompt_if_missing "API_TOKEN_SECRET" "API_TOKEN_SECRET" "1"
prompt_if_missing "ADMIN_EMAIL" "ADMIN_EMAIL"

echo "[1/8] Voraussetzungen prüfen..."
need_cmd git
need_cmd docker
docker compose version >/dev/null

echo "[2/8] Zielordner vorbereiten: ${REPO_DIR}"
run_cmd mkdir -p "${REPO_DIR}"

if [ -d "${REPO_DIR}/.git" ]; then
  echo "[3/8] Bestehendes Repo aktualisieren..."
  run_cmd git -C "${REPO_DIR}" fetch --all --tags
  run_cmd git -C "${REPO_DIR}" checkout "${AHDS_REPO_REF}"
  run_cmd git -C "${REPO_DIR}" pull --ff-only
else
  echo "[3/8] Repo klonen..."
  run_cmd git clone --branch "${AHDS_REPO_REF}" "${AHDS_REPO_URL}" "${REPO_DIR}"
fi

if [ ! -d "${TARGET_DIR}" ]; then
  echo "Fehler: Zielpfad nicht gefunden: ${TARGET_DIR}" >&2
  exit 1
fi

cd "${TARGET_DIR}"

echo "[4/8] .env vorbereiten..."
if [ ! -f ".env" ]; then
  run_cmd cp .env.example .env
fi

# Übergebene Variablen in .env schreiben
if [ "${DRY_RUN}" = "1" ]; then
  echo "[dry-run] .env würde aktualisiert (STAGING_DOMAIN/TLS/DB/Secrets)."
else
  set_env_var .env "STAGING_DOMAIN" "${STAGING_DOMAIN:-}"
  set_env_var .env "TLS_EMAIL" "${TLS_EMAIL:-}"
  set_env_var .env "POSTGRES_USER" "${POSTGRES_USER:-}"
  set_env_var .env "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"
  set_env_var .env "POSTGRES_DB" "${POSTGRES_DB:-}"
  set_env_var .env "API_TOKEN_SECRET" "${API_TOKEN_SECRET:-}"
  set_env_var .env "ADMIN_EMAIL" "${ADMIN_EMAIL:-}"
  set_env_var .env "LOGIN_MAX_FEHLVERSUCHE" "${LOGIN_MAX_FEHLVERSUCHE:-}"
  set_env_var .env "LOGIN_SPERRE_SEKUNDEN" "${LOGIN_SPERRE_SEKUNDEN:-}"
  set_env_var .env "RESET_TOKEN_TTL_SEKUNDEN" "${RESET_TOKEN_TTL_SEKUNDEN:-}"
fi

echo "[5/8] Pflichtwerte prüfen..."
# shellcheck disable=SC1091
. ./.env

require_non_empty() {
  k="$1"
  v="$2"
  if [ -z "${v}" ]; then
    echo "Fehler: ${k} fehlt in .env (oder als Env beim Aufruf)." >&2
    exit 1
  fi
}

require_non_empty "STAGING_DOMAIN" "${STAGING_DOMAIN:-}"
require_non_empty "TLS_EMAIL" "${TLS_EMAIL:-}"
require_non_empty "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"
require_non_empty "API_TOKEN_SECRET" "${API_TOKEN_SECRET:-}"
require_non_empty "ADMIN_EMAIL" "${ADMIN_EMAIL:-}"

if printf '%s' "${POSTGRES_PASSWORD}" | grep -q "bitte_"; then
  echo "Fehler: POSTGRES_PASSWORD sieht nach Platzhalter aus." >&2
  exit 1
fi
if printf '%s' "${API_TOKEN_SECRET}" | grep -q "bitte_"; then
  echo "Fehler: API_TOKEN_SECRET sieht nach Platzhalter aus." >&2
  exit 1
fi

echo "[6/8] Preflight..."
run_cmd chmod +x preflight_proxmox.sh
run_cmd ./preflight_proxmox.sh

echo "[7/8] Deploy..."
run_cmd chmod +x deploy_update.sh
run_cmd ./deploy_update.sh

if [ "${INSTALL_SYSTEMD}" = "1" ]; then
  echo "[8/8] systemd einrichten..."
  run_cmd cp systemd/ahds-staging.service /etc/systemd/system/
  run_cmd cp systemd/ahds-staging-backup.service /etc/systemd/system/
  run_cmd cp systemd/ahds-staging-backup.timer /etc/systemd/system/
  run_cmd systemctl daemon-reload
  run_cmd systemctl enable --now ahds-staging.service
  run_cmd systemctl enable --now ahds-staging-backup.timer
else
  echo "[8/8] systemd übersprungen (INSTALL_SYSTEMD=${INSTALL_SYSTEMD})."
fi

echo "Installation abgeschlossen."
echo "Nächster Schritt: ./healthcheck_proxmox.sh"
