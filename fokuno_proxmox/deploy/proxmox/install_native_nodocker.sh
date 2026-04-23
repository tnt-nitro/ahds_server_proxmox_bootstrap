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

# Weniger Locale-Warnungen bei psql/postgres-Client (z. B. in minimalen CTs).
export LC_ALL=C
export LANG=C

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
API_DIR="${REPO_ROOT}/fokuno_proxmox/deploy/staging_api"
APP_DIR="/opt/ahds-native"
VENV_DIR="${APP_DIR}/venv"
ENV_FILE="${APP_DIR}/.env"
APP_USER="ahds"
APP_GROUP="ahds"
SYSTEMD_SERVICE="ahds-staging-api"
NGINX_SITE="ahds-staging"
AUTO_MODE=0

for arg in "$@"; do
  case "${arg}" in
    --non-interactive)
      AUTO_MODE=1
      ;;
    *)
      echo "Unbekannter Parameter: ${arg}" >&2
      echo "Erlaubt: --non-interactive" >&2
      exit 1
      ;;
  esac
done

wait_for_api_health() {
  local url="$1"
  local max="${2:-45}"
  local i=0
  echo "Warte auf API unter ${url} (max. ${max}s)..."
  while (( i < max )); do
    if curl -fsS --connect-timeout 2 --max-time 5 "${url}" >/dev/null 2>&1; then
      echo "API antwortet nach ca. $((i + 1))s."
      return 0
    fi
    ((i++)) || true
    sleep 1
  done
  echo "Fehler: API antwortet nicht auf ${url}" >&2
  systemctl status "${SYSTEMD_SERVICE}.service" --no-pager -l || true
  journalctl -u "${SYSTEMD_SERVICE}.service" -n 80 --no-pager || true
  return 1
}

as_user() {
  local user="$1"
  shift
  if command -v runuser >/dev/null 2>&1; then
    runuser -u "${user}" -- "$@"
  else
    su -s /bin/sh -c "$(printf "%q " "$@")" "${user}"
  fi
}

domain_valid() {
  local d="$1"
  [[ "${d}" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]
}

mail_valid() {
  local m="$1"
  [[ "${m}" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]
}

prompt_required() {
  local key="$1"
  local label="$2"
  local hinweis="$3"
  local secret="${4:-0}"
  local value=""
  while true; do
    echo
    echo "${label}"
    echo "  ${hinweis}"
    if [[ "${secret}" == "1" ]]; then
      read -r -s -p "> " value
      echo
    else
      read -r -p "> " value
    fi
    if [[ -z "${value}" ]]; then
      echo "Eingabe fehlt (${key}). Bitte erneut eingeben." >&2
      continue
    fi
    printf -v "${key}" "%s" "${value}"
    return 0
  done
}

prompt_secret_confirm() {
  local key="$1"
  local label="$2"
  local hinweis="$3"
  local value=""
  local confirm=""
  while true; do
    echo
    echo "${label}"
    echo "  ${hinweis}"
    read -r -s -p "> " value
    echo
    if [[ -z "${value}" ]]; then
      echo "Eingabe fehlt (${key}). Bitte erneut eingeben." >&2
      continue
    fi
    read -r -s -p "> Bitte zur Bestätigung erneut eingeben: " confirm
    echo
    if [[ "${value}" != "${confirm}" ]]; then
      echo "Eingaben stimmen nicht überein. Bitte erneut eingeben." >&2
      continue
    fi
    printf -v "${key}" "%s" "${value}"
    return 0
  done
}

prompt_optional() {
  local key="$1"
  local label="$2"
  local hinweis="$3"
  local value=""
  echo
  echo "${label}"
  echo "  ${hinweis}"
  read -r -p "> " value
  printf -v "${key}" "%s" "${value}"
}

POSTGRES_DB="ahds_staging"
POSTGRES_USER="ahds"
APP_ENV="staging"

echo "AhDs Native Installer (ohne Docker)"
echo "===================================="
echo
echo "Ablauf:"
echo "  1) Systempakete installieren"
echo "  2) Eingaben abfragen (mit Erklärungen)"
echo "  3) API + Datenbank + NGINX + TLS einrichten"
echo

echo "[1/9] Pakete installieren..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  git curl ca-certificates gnupg \
  python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  nginx certbot python3-certbot-nginx

if [[ -t 1 ]]; then
  clear
fi

if [[ "${AUTO_MODE}" -eq 1 ]]; then
  : "${STAGING_DOMAIN:?STAGING_DOMAIN fehlt}"
  : "${TLS_EMAIL:?TLS_EMAIL fehlt}"
  : "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD fehlt}"
  : "${API_TOKEN_SECRET:?API_TOKEN_SECRET fehlt}"
  : "${ADMIN_EMAIL:?ADMIN_EMAIL fehlt}"
  DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-}"
else
  echo "AhDs Konfiguration"
  echo "=================="
  echo "Bitte jetzt die benötigten Werte eingeben."

  prompt_required STAGING_DOMAIN \
    "1/6 Domain für Staging-API" \
    "Beispiel: ahdsserver.duckdns.org (genau diese Ziel-Domain eingeben)."

  prompt_required TLS_EMAIL \
    "2/6 TLS E-Mail (Let's Encrypt Kontakt)" \
    "Beispiel: dein.name@example.org"

  prompt_secret_confirm POSTGRES_PASSWORD \
    "3/6 PostgreSQL Passwort" \
    "Starkes Passwort für DB-Benutzer '${POSTGRES_USER}' (mit Zweiteingabe)."

  prompt_secret_confirm API_TOKEN_SECRET \
    "4/6 API Token Secret" \
    "Langer, zufälliger Wert für Signierung der API-Tokens (mit Zweiteingabe)."

  prompt_required ADMIN_EMAIL \
    "5/6 Admin E-Mail für die API" \
    "Beispiel: admin@example.org"

  prompt_optional DUCKDNS_TOKEN \
    "6/6 DuckDNS Token (optional)" \
    "Nur nötig, wenn dieses Script den DuckDNS-Cronjob setzen soll. Leer lassen, wenn der DuckDNS-Update-Job bereits separat eingerichtet ist."
fi

if ! domain_valid "${STAGING_DOMAIN}"; then
  echo "Ungültige Domain: ${STAGING_DOMAIN}" >&2
  exit 1
fi
if ! mail_valid "${TLS_EMAIL}"; then
  echo "Ungültige E-Mail: ${TLS_EMAIL}" >&2
  exit 1
fi
if ! mail_valid "${ADMIN_EMAIL}"; then
  echo "Ungültige Admin-E-Mail: ${ADMIN_EMAIL}" >&2
  exit 1
fi

echo
echo "[2/9] System-User und App-Verzeichnis..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${APP_DIR}" --create-home --shell /usr/sbin/nologin "${APP_USER}"
fi
mkdir -p "${APP_DIR}"
rm -rf "${APP_DIR}/staging_api"
cp -r "${API_DIR}" "${APP_DIR}/staging_api"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"

echo "[3/9] Python venv und Abhängigkeiten..."
as_user "${APP_USER}" python3 -m venv "${VENV_DIR}"
as_user "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip
as_user "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/staging_api/requirements.txt"

echo "[4/9] Postgres DB/User..."
as_user postgres psql -v ON_ERROR_STOP=1 <<SQL
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

DB_EXISTS="$(as_user postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'" | tr -d '[:space:]')"
if [[ "${DB_EXISTS}" != "1" ]]; then
  as_user postgres createdb -O "${POSTGRES_USER}" "${POSTGRES_DB}"
fi

echo "[5/9] Env-Datei für Service..."
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

echo "[6/9] systemd Service einrichten..."
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
systemctl restart "${SYSTEMD_SERVICE}.service" 2>/dev/null || true

echo "[7/9] Lokalen API-Healthcheck prüfen..."
wait_for_api_health "http://127.0.0.1:8000/health" 60

ACME_WEBROOT="/var/www/ahds-acme"
mkdir -p "${ACME_WEBROOT}/.well-known/acme-challenge"
chown -R www-data:www-data "${ACME_WEBROOT}" 2>/dev/null || chown -R nginx:nginx "${ACME_WEBROOT}" 2>/dev/null || true

echo "[8/9] NGINX Reverse Proxy (HTTP + ACME-Webroot)..."
cat > "/etc/nginx/sites-available/${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${STAGING_DOMAIN};

    # Muss VOR location / stehen: Let's Encrypt HTTP-01
    location ^~ /.well-known/acme-challenge/ {
        root ${ACME_WEBROOT};
        default_type "text/plain";
        try_files \$uri =404;
    }

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

echo "[9/9] TLS via Certbot (Webroot)..."
set +e
certbot certonly \
  --webroot -w "${ACME_WEBROOT}" \
  -d "${STAGING_DOMAIN}" \
  -m "${TLS_EMAIL}" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring
CERTBOT_RC=$?
set -e
if [[ "${CERTBOT_RC}" -ne 0 ]]; then
  echo
  echo "Certbot ist fehlgeschlagen (Exit ${CERTBOT_RC}). Häufige Ursachen:" >&2
  echo "  - Port 80 von außen muss auf DIESE Maschine zeigen (Router-Portweiterleitung auf diese IP)." >&2
  echo "  - ${STAGING_DOMAIN} muss per DNS (z. B. DuckDNS) auf die öffentliche IP zeigen, die hier ankommt." >&2
  echo "  - Kein anderer Dienst darf Port 80 belegen oder eine andere Antwort liefern als dieses NGINX." >&2
  echo "Prüfen (lokal, mit Host-Header):" >&2
  echo "  curl -sI -H 'Host: ${STAGING_DOMAIN}' http://127.0.0.1/.well-known/acme-challenge/test || true" >&2
  echo "Log: /var/log/letsencrypt/letsencrypt.log" >&2
  exit "${CERTBOT_RC}"
fi

SSL_FULLCHAIN="/etc/letsencrypt/live/${STAGING_DOMAIN}/fullchain.pem"
SSL_PRIVKEY="/etc/letsencrypt/live/${STAGING_DOMAIN}/privkey.pem"
if [[ ! -f "${SSL_FULLCHAIN}" ]] || [[ ! -f "${SSL_PRIVKEY}" ]]; then
  echo "Fehler: Zertifikatdateien fehlen nach Certbot." >&2
  exit 1
fi

echo "NGINX: HTTPS aktivieren..."
SSL_EXTRA=""
if [[ -f /etc/letsencrypt/options-ssl-nginx.conf ]]; then
  SSL_EXTRA="include /etc/letsencrypt/options-ssl-nginx.conf;"
fi
if [[ -f /etc/letsencrypt/ssl-dhparams.pem ]]; then
  SSL_EXTRA="${SSL_EXTRA}
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;"
fi

cat > "/etc/nginx/sites-available/${NGINX_SITE}" <<EOF
server {
    listen 80;
    server_name ${STAGING_DOMAIN};

    location ^~ /.well-known/acme-challenge/ {
        root ${ACME_WEBROOT};
        default_type "text/plain";
        try_files \$uri =404;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name ${STAGING_DOMAIN};

    ssl_certificate ${SSL_FULLCHAIN};
    ssl_certificate_key ${SSL_PRIVKEY};
    ${SSL_EXTRA}

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

nginx -t
systemctl reload nginx

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
echo "Installiert auf Host: $(hostname)"
echo "Hinweis: Dieses Script erstellt keinen Proxmox-CT; es installiert nativ auf dem aktuellen System."
echo "Tests:"
echo "  curl -I https://${STAGING_DOMAIN}/health"
echo "  curl -I https://${STAGING_DOMAIN}/ready"
echo "  curl -I https://${STAGING_DOMAIN}/v1/meta/version"
