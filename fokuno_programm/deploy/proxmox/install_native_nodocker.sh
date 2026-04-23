#!/usr/bin/env bash
set -euo pipefail

# AhDs Native Installer (ohne Docker)
# Ziel: Eine Ausführung, wenige Eingaben, danach lauffähiges Staging.
#
# Voraussetzungen:
# - Debian/Ubuntu (auch Proxmox Host technisch möglich; produktiv besser in VM/LXC)
# - Root-Rechte
#
# Start:
#   bash install_native_nodocker.sh

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte als root ausführen." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
API_DIR="${REPO_ROOT}/fokuno_programm/deploy/staging_api"
APP_DIR="/opt/ahds-native"
VENV_DIR="${APP_DIR}/venv"
ENV_FILE="${APP_DIR}/.env"
APP_USER="ahds"
APP_GROUP="ahds"
SYSTEMD_SERVICE="ahds-staging-api"
NGINX_SITE="ahds-staging"

prompt() {
  local key="$1"
  local label="$2"
  local secret="${3:-0}"
  local value=""
  if [[ "${secret}" == "1" ]]; then
    read -r -s -p "${label}: " value
    echo
  else
    read -r -p "${label}: " value
  fi
  if [[ -z "${value}" ]]; then
    echo "Wert darf nicht leer sein: ${key}" >&2
    exit 1
  fi
  printf -v "${key}" "%s" "${value}"
}

echo "AhDs Native Installer (ohne Docker)"
echo "===================================="
echo
prompt STAGING_DOMAIN "Domain (z. B. ahdsserver.duckdns.org)"
prompt TLS_EMAIL "TLS E-Mail"
prompt POSTGRES_PASSWORD "Postgres Passwort" 1
prompt API_TOKEN_SECRET "API Token Secret (lang/stark)" 1
prompt ADMIN_EMAIL "Admin E-Mail"
read -r -p "DuckDNS Token (optional, Enter = überspringen): " DUCKDNS_TOKEN

POSTGRES_DB="ahds_staging"
POSTGRES_USER="ahds"
APP_ENV="staging"

echo
echo "[1/8] Pakete installieren..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  git curl ca-certificates gnupg \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx certbot python3-certbot-nginx

echo "[2/8] System-User und App-Verzeichnis..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${APP_DIR}" --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi
mkdir -p "${APP_DIR}"
cp -r "${API_DIR}" "${APP_DIR}/staging_api"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

echo "[3/8] Python venv und Abhängigkeiten..."
sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/staging_api/requirements.txt"

echo "[4/8] Postgres DB/User..."
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${POSTGRES_USER}') THEN
      CREATE ROLE ${POSTGRES_USER} LOGIN PASSWORD '${POSTGRES_PASSWORD}';
   ELSE
      ALTER ROLE ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
   END IF;
END
\$\$;
SQL

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}') THEN
      CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};
   END IF;
END
\$\$;
SQL

echo "[5/8] Env-Datei für Service..."
cat > "${ENV_FILE}" <<EOF
APP_ENV=${APP_ENV}
API_TOKEN_SECRET=${API_TOKEN_SECRET}
ADMIN_EMAIL=${ADMIN_EMAIL}
LOGIN_MAX_FEHLVERSUCHE=5
LOGIN_SPERRE_SEKUNDEN=900
RESET_TOKEN_TTL_SEKUNDEN=1800
PGHOST=127.0.0.1
PGPORT=5432
PGUSER=${POSTGRES_USER}
PGPASSWORD=${POSTGRES_PASSWORD}
PGDATABASE=${POSTGRES_DB}
EOF
chown "${APP_USER}:${APP_GROUP}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

echo "[6/8] systemd Service einrichten..."
cat > "/etc/systemd/system/${SYSTEMD_SERVICE}.service" <<EOF
[Unit]
Description=AhDs Staging API (native)
After=network-online.target postgresql.service
Wants=network-online.target
Requires=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}/staging_api
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SYSTEMD_SERVICE}.service"

echo "[7/8] NGINX Reverse Proxy..."
cat > "/etc/nginx/sites-available/${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${STAGING_DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${NGINX_SITE}" "/etc/nginx/sites-enabled/${NGINX_SITE}"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "[8/8] TLS via Certbot..."
certbot --nginx -d "${STAGING_DOMAIN}" -m "${TLS_EMAIL}" --agree-tos --non-interactive --redirect

if [[ -n "${DUCKDNS_TOKEN:-}" ]]; then
  echo "[DuckDNS] Updater einrichten..."
  mkdir -p /opt/duckdns
  cat > /opt/duckdns/duck.sh <<EOF
url=https://www.duckdns.org/update?domains=${STAGING_DOMAIN%%.duckdns.org}&token=${DUCKDNS_TOKEN}&ip=
EOF
  chmod 700 /opt/duckdns/duck.sh
  (crontab -l 2>/dev/null; echo "*/5 * * * * /usr/bin/curl -s \"\$(cat /opt/duckdns/duck.sh)\" >/dev/null 2>&1") | crontab -
fi

echo
echo "Fertig."
echo "Tests:"
echo "  curl -I https://${STAGING_DOMAIN}/health"
echo "  curl -I https://${STAGING_DOMAIN}/ready"
echo "  curl -I https://${STAGING_DOMAIN}/v1/meta/version"
