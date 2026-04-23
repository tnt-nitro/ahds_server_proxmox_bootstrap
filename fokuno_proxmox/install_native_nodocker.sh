#!/usr/bin/env bash
set -euo pipefail

# Zentrale Einstiegsschicht für native Installation ohne CT.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_SCRIPT="${REPO_ROOT}/fokuno_proxmox/deploy/proxmox/install_native_nodocker.sh"

if [[ ! -f "${TARGET_SCRIPT}" ]]; then
  echo "Fehler: Zielscript nicht gefunden: ${TARGET_SCRIPT}" >&2
  exit 1
fi

exec bash "${TARGET_SCRIPT}" "$@"
