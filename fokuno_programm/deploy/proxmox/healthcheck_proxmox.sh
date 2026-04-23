#!/usr/bin/env sh
set -eu

# Schneller Live-Check für Proxmox-Staging.
# Aufruf im Ordner deploy/proxmox:
#   chmod +x healthcheck_proxmox.sh
#   ./healthcheck_proxmox.sh

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
else
  echo "Fehler: .env nicht gefunden (im Ordner deploy/proxmox ausführen)." >&2
  exit 1
fi

if [ -z "${STAGING_DOMAIN:-}" ]; then
  echo "Fehler: STAGING_DOMAIN nicht gesetzt." >&2
  exit 1
fi

BASE_URL="https://${STAGING_DOMAIN}"

echo "[1/5] Container-Status"
docker compose --env-file .env -f staging-compose.proxmox.yml ps

echo "[2/5] API /health"
curl -fsS "${BASE_URL}/health" | python -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok', d; print(d)"

echo "[3/5] API /ready"
curl -fsS "${BASE_URL}/ready" | python -c "import sys,json; d=json.load(sys.stdin); assert d.get('db')=='ok', d; print(d)"

echo "[4/5] API /v1/meta/version (mit Client-Major-Header)"
curl -fsS -H "x-client-api-major: v1" "${BASE_URL}/v1/meta/version" | python -c "import sys,json; d=json.load(sys.stdin); assert d.get('api_major')=='v1', d; print(d)"

echo "[5/5] Deprecation-Meta"
curl -fsS -H "x-client-api-major: v1" "${BASE_URL}/v1/meta/deprecations" | python -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d,list), d; print({'deprecations': len(d)})"

echo "Healthcheck erfolgreich."
