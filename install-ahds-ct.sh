#!/usr/bin/env bash
set -euo pipefail

# AhDs Bootstrap für Proxmox:
# - klont/aktualisiert privates Repo unter /opt/ahds
# - startet den CT-Installer ohne Docker

if [[ "${EUID}" -ne 0 ]]; then
  echo "Bitte als root ausführen." >&2
  exit 1
fi

for cmd in git bash; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Fehlender Befehl: ${cmd}" >&2
    exit 1
  fi
done

TARGET_DIR="/opt/ahds"
GITHUB_OWNER_DEFAULT="tnt-nitro"
PRIVATE_REPO_DEFAULT="fokuno"
INSTALLER_REL="ahds_server_proxmox/install_proxmox_ct_nodocker.sh"

read -r -p "GitHub-Owner [${GITHUB_OWNER_DEFAULT}]: " GITHUB_OWNER_INPUT
GITHUB_OWNER="${GITHUB_OWNER_INPUT:-${GITHUB_OWNER_DEFAULT}}"

read -r -p "Privates Repo [${PRIVATE_REPO_DEFAULT}]: " PRIVATE_REPO_INPUT
PRIVATE_REPO="${PRIVATE_REPO_INPUT:-${PRIVATE_REPO_DEFAULT}}"

if [[ ! "${GITHUB_OWNER}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Ungueltiger GitHub-Owner: ${GITHUB_OWNER}" >&2
  exit 1
fi

if [[ ! "${PRIVATE_REPO}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Ungueltiger Repo-Name: ${PRIVATE_REPO}" >&2
  exit 1
fi

PRIVATE_REPO_SSH="git@github.com:${GITHUB_OWNER}/${PRIVATE_REPO}.git"

echo "AhDs Proxmox Bootstrap"
echo "======================"
echo "Zielpfad: ${TARGET_DIR}"
echo "Repo:     ${PRIVATE_REPO_SSH}"
echo

if [[ -d "${TARGET_DIR}/.git" ]]; then
  echo "[1/3] Bestehendes Repo aktualisieren..."
  git -C "${TARGET_DIR}" fetch --all --prune
  git -C "${TARGET_DIR}" checkout main
  git -C "${TARGET_DIR}" pull --ff-only origin main
else
  echo "[1/3] Repo neu klonen..."
  rm -rf "${TARGET_DIR}"
  git clone "${PRIVATE_REPO_SSH}" "${TARGET_DIR}"
fi

INSTALLER="${TARGET_DIR}/${INSTALLER_REL}"
if [[ ! -f "${INSTALLER}" ]]; then
  echo "Installer nicht gefunden: ${INSTALLER}" >&2
  exit 1
fi

echo "[2/3] Installer ausführbar machen..."
chmod +x "${INSTALLER}"

echo "[3/3] CT-Installer starten..."
echo "Hinweis: Danach folgen interaktive Fragen (CT-ID, Domain, Secrets ...)."
echo
exec "${INSTALLER}"
