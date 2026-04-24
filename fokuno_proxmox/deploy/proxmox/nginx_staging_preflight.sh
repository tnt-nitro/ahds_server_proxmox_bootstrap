#!/usr/bin/env bash
set -euo pipefail

# Kurz prüfen: NGINX + TLS für AhDs-Staging (auf dem CT/Host wie installiert).
# Wenig Ausgabe bei Erfolg; bei Fehler ein paar konkrete Zeilen.
#
# Nutzung:
#   bash nginx_staging_preflight.sh
#   STAGING_DOMAIN=deine.domain bash nginx_staging_preflight.sh
#
# Domain wird sonst aus /opt/ahds-native/.env gelesen (Zeile STAGING_DOMAIN=).

ENV_FILE="${AHDS_RUNTIME_ENV_FILE:-/opt/ahds-native/.env}"

domain_lesen() {
  if [[ -n "${STAGING_DOMAIN:-}" ]]; then
    printf "%s" "${STAGING_DOMAIN}"
    return 0
  fi
  if [[ -f "${ENV_FILE}" ]]; then
    grep -E '^[[:space:]]*STAGING_DOMAIN=' "${ENV_FILE}" 2>/dev/null | head -n1 | cut -d= -f2- | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
  fi
}

DOMAIN="$(domain_lesen | tr -d '[:space:]')"
if [[ -z "${DOMAIN}" ]]; then
  echo "Keine STAGING_DOMAIN gesetzt und nicht in ${ENV_FILE} gefunden." >&2
  exit 1
fi

echo "== Domain: ${DOMAIN} =="

echo "== NGINX Konfigurationstest =="
set +e
NG_OUT="$(nginx -t 2>&1)"
NG_RC=$?
set -e
echo "${NG_OUT}" | sed -n '1,8p'
[[ "${NG_RC}" -eq 0 ]] || exit "${NG_RC}"

echo "== Port 80 (Loopback, Host-Header) → /health =="
code80="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 12 \
  -H "Host: ${DOMAIN}" "http://127.0.0.1/health" || echo "000")"
echo "HTTP ${code80}"
if [[ "${code80}" != "200" && "${code80}" != "301" && "${code80}" != "302" ]]; then
  echo "Unerwartet: nach TLS-Umstellung ist 301/302 nach HTTPS üblich, sonst 200." >&2
fi

echo "== Port 443 (Loopback, SNI) → /health =="
code443="$(curl -skS -o /dev/null -w "%{http_code}" --connect-timeout 3 --max-time 12 \
  --resolve "${DOMAIN}:443:127.0.0.1" "https://${DOMAIN}/health" || echo "000")"
echo "HTTP ${code443}"
if [[ "${code443}" != "200" ]]; then
  echo "Hinweis: Ohne gültiges Zertifikat oder ohne HTTPS-Server bleibt das rot." >&2
fi

echo "OK — Preflight beendet."
