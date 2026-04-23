#!/usr/bin/env bash
set -euo pipefail

# AhDs Proxmox CT Installer (ohne Docker)
# Erstellt einen eigenen LXC-CT und installiert darin die native Staging-API.

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte als root auf dem Proxmox-Host ausführen." >&2
  exit 1
fi

for cmd in pct pveam pvesh pvesm tar awk sed; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Fehlender Befehl: ${cmd}" >&2
    exit 1
  fi
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
SOURCE_INSTALLER="${SCRIPT_DIR}/install_native_nodocker.sh"
SOURCE_STAGING_API="${REPO_ROOT}/fokuno_programm/deploy/staging_api"

if [[ ! -f "${SOURCE_INSTALLER}" ]]; then
  echo "Installer nicht gefunden: ${SOURCE_INSTALLER}" >&2
  exit 1
fi
if [[ ! -d "${SOURCE_STAGING_API}" ]]; then
  echo "staging_api nicht gefunden: ${SOURCE_STAGING_API}" >&2
  exit 1
fi

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
    echo "Eingabe fehlt (${key})." >&2
    exit 1
  fi
  printf -v "${key}" "%s" "${value}"
}

prompt_default() {
  local key="$1"
  local label="$2"
  local hint="$3"
  local default_val="$4"
  local value=""
  echo
  echo "${label}"
  echo "  ${hint}"
  read -r -p "> [${default_val}] " value
  if [[ -z "${value}" ]]; then
    value="${default_val}"
  fi
  printf -v "${key}" "%s" "${value}"
}

write_env_line() {
  local key="$1"
  local value="$2"
  printf "%s=%q\n" "${key}" "${value}" >> "${ENV_FILE}"
}

if [[ -t 1 ]]; then
  clear
fi
echo "AhDs Proxmox CT-Installer (ohne Docker)"
echo "======================================="
echo "Dieses Script:"
echo "  1) erstellt einen eigenen LXC-Container (CT)"
echo "  2) installiert AhDs Staging nativ im CT"
echo "  3) startet den Dienst im CT"
echo
echo "Hinweis:"
echo "  Für TLS mit Let's Encrypt muss deine Domain auf die IP des CT zeigen"
echo "  (bzw. Port-Forwarding im Router auf die CT-IP)."

DEFAULT_CTID="$(pvesh get /cluster/nextid 2>/dev/null || echo 120)"

prompt_default CTID "CT-ID" "Sichtbare Container-ID in Proxmox." "${DEFAULT_CTID}"
prompt_default CT_HOSTNAME "CT-Hostname" "Name des Containers in Proxmox." "ahds-staging"
prompt_default CT_STORAGE "CT Storage" "Beispiel: local-lvm" "local-lvm"
prompt_default TEMPLATE_STORAGE "Template Storage" "Beispiel: local" "local"
prompt_default CT_CORES "CPU Cores" "Empfehlung für Start: 2" "2"
prompt_default CT_MEMORY "RAM in MB" "Empfehlung für Start: 2048" "2048"
prompt_default CT_DISK_GB "Disk in GB" "Empfehlung für Start: 8" "8"
prompt_default CT_BRIDGE "Netzwerk-Bridge" "Meist vmbr0" "vmbr0"

prompt_required STAGING_DOMAIN \
  "Domain für die API" \
  "Beispiel: ahdsserver.duckdns.org"
if ! domain_valid "${STAGING_DOMAIN}"; then
  echo "Ungültige Domain: ${STAGING_DOMAIN}" >&2
  exit 1
fi

prompt_required TLS_EMAIL \
  "TLS E-Mail" \
  "Let's Encrypt Kontaktadresse (z. B. name@example.org)."
if ! mail_valid "${TLS_EMAIL}"; then
  echo "Ungültige E-Mail: ${TLS_EMAIL}" >&2
  exit 1
fi

prompt_required POSTGRES_PASSWORD \
  "PostgreSQL Passwort" \
  "Starkes Passwort für den Datenbank-Benutzer." \
  1

prompt_required API_TOKEN_SECRET \
  "API Token Secret" \
  "Langer zufälliger Wert für Signierung der Tokens." \
  1

prompt_required ADMIN_EMAIL \
  "Admin E-Mail" \
  "Beispiel: admin@example.org"
if ! mail_valid "${ADMIN_EMAIL}"; then
  echo "Ungültige Admin-E-Mail: ${ADMIN_EMAIL}" >&2
  exit 1
fi

prompt_default DUCKDNS_TOKEN \
  "DuckDNS Token (optional)" \
  "Leer lassen, wenn DuckDNS bereits getrennt läuft." \
  ""

echo
echo "[1/8] Debian-12 Template prüfen..."
pveam update
TEMPLATE_NAME="$(pveam available --section system | awk '/debian-12-standard_.*_amd64.tar.zst/ {print $2; exit}')"
if [[ -z "${TEMPLATE_NAME}" ]]; then
  echo "Kein Debian-12 LXC-Template gefunden." >&2
  exit 1
fi
if ! pveam list "${TEMPLATE_STORAGE}" | awk '{print $2}' | grep -qx "${TEMPLATE_NAME}"; then
  pveam download "${TEMPLATE_STORAGE}" "${TEMPLATE_NAME}"
fi

echo "[2/8] CT ${CTID} erstellen..."
if pct status "${CTID}" >/dev/null 2>&1; then
  echo "CT-ID ${CTID} existiert bereits. Bitte andere CT-ID wählen." >&2
  exit 1
fi
pct create "${CTID}" "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE_NAME}" \
  -hostname "${CT_HOSTNAME}" \
  -cores "${CT_CORES}" \
  -memory "${CT_MEMORY}" \
  -swap 512 \
  -rootfs "${CT_STORAGE}:${CT_DISK_GB}" \
  -net0 "name=eth0,bridge=${CT_BRIDGE},ip=dhcp" \
  -unprivileged 1 \
  -onboot 1

echo "[3/8] CT starten..."
pct start "${CTID}"
sleep 3

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

PAYLOAD_ROOT="${WORK_DIR}/ahds-bootstrap"
mkdir -p "${PAYLOAD_ROOT}/fokuno_programm/deploy/proxmox"
mkdir -p "${PAYLOAD_ROOT}/fokuno_programm/deploy"
cp "${SOURCE_INSTALLER}" "${PAYLOAD_ROOT}/fokuno_programm/deploy/proxmox/install_native_nodocker.sh"
cp -r "${SOURCE_STAGING_API}" "${PAYLOAD_ROOT}/fokuno_programm/deploy/staging_api"
chmod +x "${PAYLOAD_ROOT}/fokuno_programm/deploy/proxmox/install_native_nodocker.sh"

ENV_FILE="${PAYLOAD_ROOT}/installer.env"
write_env_line STAGING_DOMAIN "${STAGING_DOMAIN}"
write_env_line TLS_EMAIL "${TLS_EMAIL}"
write_env_line POSTGRES_PASSWORD "${POSTGRES_PASSWORD}"
write_env_line API_TOKEN_SECRET "${API_TOKEN_SECRET}"
write_env_line ADMIN_EMAIL "${ADMIN_EMAIL}"
write_env_line DUCKDNS_TOKEN "${DUCKDNS_TOKEN}"

echo "[4/8] Installer-Payload in CT kopieren..."
tar -C "${WORK_DIR}" -czf "${WORK_DIR}/ahds-bootstrap.tar.gz" ahds-bootstrap
pct push "${CTID}" "${WORK_DIR}/ahds-bootstrap.tar.gz" /root/ahds-bootstrap.tar.gz

echo "[5/8] Payload entpacken..."
pct exec "${CTID}" -- bash -lc "rm -rf /root/ahds-bootstrap && tar -xzf /root/ahds-bootstrap.tar.gz -C /root"

echo "[6/8] Native Installation im CT starten..."
pct exec "${CTID}" -- bash -lc "cd /root/ahds-bootstrap/fokuno_programm/deploy/proxmox && set -a && . /root/ahds-bootstrap/installer.env && set +a && ./install_native_nodocker.sh --non-interactive"

echo "[7/8] CT-IP ermitteln..."
CT_IP="$(pct exec "${CTID}" -- bash -lc "hostname -I | awk '{print \$1}'" | tr -d '\r')"

echo "[8/8] Zusammenfassung"
echo
echo "Fertig."
echo "CT-ID:        ${CTID}"
echo "CT-Hostname:  ${CT_HOSTNAME}"
echo "CT-IP:        ${CT_IP:-unbekannt}"
echo "Service:      ahds-staging-api.service (im CT)"
echo
echo "Wichtig für TLS/Domain:"
echo "  Domain ${STAGING_DOMAIN} muss auf die CT-IP zeigen (${CT_IP:-?})"
echo "  oder Router-Portforwarding 80/443 auf diese CT-IP setzen."
echo
echo "Nützliche Befehle:"
echo "  pct status ${CTID}"
echo "  pct enter ${CTID}"
echo "  pct stop ${CTID}"
echo "  pct start ${CTID}"
echo "  pct destroy ${CTID} --purge 1"
