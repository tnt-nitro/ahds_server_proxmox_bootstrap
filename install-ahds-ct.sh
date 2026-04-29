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
INSTALLER_REL="install_proxmox_ct_nodocker.sh"

read -r -p "GitHub-Owner: " GITHUB_OWNER_INPUT
GITHUB_OWNER="${GITHUB_OWNER_INPUT}"
if [[ -z "${GITHUB_OWNER}" ]]; then
  echo "GitHub-Owner darf nicht leer sein." >&2
  exit 1
fi

read -r -p "Repo: " PRIVATE_REPO_INPUT
PRIVATE_REPO="${PRIVATE_REPO_INPUT}"
if [[ -z "${PRIVATE_REPO}" ]]; then
  echo "Repo darf nicht leer sein." >&2
  exit 1
fi

if [[ ! "${GITHUB_OWNER}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Ungueltiger GitHub-Owner: ${GITHUB_OWNER}" >&2
  exit 1
fi

if [[ ! "${PRIVATE_REPO}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Ungueltiger Repo-Name: ${PRIVATE_REPO}" >&2
  exit 1
fi

PRIVATE_REPO_SSH="git@github.com:${GITHUB_OWNER}/${PRIVATE_REPO}.git"
PRIVATE_REPO_HTTPS="https://github.com/${GITHUB_OWNER}/${PRIVATE_REPO}.git"

echo "AhDs Proxmox Bootstrap"
echo "======================"
echo "Zielpfad: ${TARGET_DIR}"
echo "Repo:     ${PRIVATE_REPO_SSH}"
echo

normalize_repo_url() {
  # Vereinheitlicht git-URL-Formen für einen Vergleich.
  # Beispiel:
  #   git@github.com:owner/repo.git -> owner/repo
  #   https://github.com/owner/repo.git -> owner/repo
  local url="$1"
  url="${url%.git}"
  url="${url#https://github.com/}"
  url="${url#git@github.com:}"
  url="${url#ssh://git@github.com/}"
  echo "$url"
}

DESIRED_REPO_NORM="$(normalize_repo_url "${PRIVATE_REPO_SSH}")"

clone_repo() {
  # Versucht zuerst per SSH zu klonen, und faellt auf HTTPS zurueck.
  # Das hilft, wenn auf dem Proxmox kein SSH-Deploy-Key eingerichtet ist.
  local ssh_url="$1"
  local https_url="$2"
  local dest="$3"

  rm -rf "${dest}"
  if git clone "${ssh_url}" "${dest}"; then
    return 0
  fi

  echo "SSH clone fehlgeschlagen, versuche HTTPS..." >&2
  rm -rf "${dest}"

  # Kein interaktives Username/Passwort anstoßen (sonst haengt es in unattended runs).
  # Wenn HTTPS wirklich frei ist, sollte es ohne Credentials funktionieren.
  if GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false git clone "${https_url}" "${dest}"; then
    return 0
  fi

  echo "HTTPS clone ohne Credentials fehlgeschlagen." >&2
  echo "Falls das Repo privat ist: GitHub Token zum Klonen setzen." >&2
  read -r -s -p "GitHub Token (nur Clone; leer = abbrechen): " GITHUB_TOKEN_INPUT
  echo >&2

  if [[ -z "${GITHUB_TOKEN_INPUT}" ]]; then
    echo "Abgebrochen ohne Token." >&2
    return 1
  fi

  # Token in der URL nutzen; aus Sicherheitsgründen nicht ausgeben.
  # Für GitHub PAT funktioniert typischerweise x-access-token.
  local token_url
  token_url="https://x-access-token:${GITHUB_TOKEN_INPUT}@github.com/${GITHUB_OWNER}/${PRIVATE_REPO}.git"

  rm -rf "${dest}"
  git clone "${token_url}" "${dest}"
}

if [[ -d "${TARGET_DIR}/.git" ]]; then
  echo "[1/3] Bestehendes Repo aktualisieren..."
  CURRENT_REPO_URL="$(git -C "${TARGET_DIR}" remote get-url origin 2>/dev/null || true)"
  CURRENT_REPO_NORM="$(normalize_repo_url "${CURRENT_REPO_URL}")"

  if [[ -n "${CURRENT_REPO_URL}" && "${CURRENT_REPO_NORM}" != "${DESIRED_REPO_NORM}" ]]; then
    echo "[1/3] Repo passt nicht (ist: ${CURRENT_REPO_URL}). Reclone: ${PRIVATE_REPO_SSH}"
    clone_repo "${PRIVATE_REPO_SSH}" "${PRIVATE_REPO_HTTPS}" "${TARGET_DIR}"
  else
    git -C "${TARGET_DIR}" fetch --all --prune
    git -C "${TARGET_DIR}" checkout main
    git -C "${TARGET_DIR}" pull --ff-only origin main
  fi
else
  echo "[1/3] Repo neu klonen..."
  clone_repo "${PRIVATE_REPO_SSH}" "${PRIVATE_REPO_HTTPS}" "${TARGET_DIR}"
fi

INSTALLER=""
INSTALLER_CANDIDATES=(
  "${TARGET_DIR}/${INSTALLER_REL}"
  "${TARGET_DIR}/ahds_server_proxmox/install_proxmox_ct_nodocker.sh"
  "${TARGET_DIR}/install_proxmox_ct_nodocker.sh"
  "${TARGET_DIR}/ahds_server_proxmox/deploy/proxmox/install_proxmox_ct_nodocker.sh"
  "${TARGET_DIR}/deploy/proxmox/install_proxmox_ct_nodocker.sh"
)
for c in "${INSTALLER_CANDIDATES[@]}"; do
  if [[ -f "${c}" ]]; then
    INSTALLER="${c}"
    break
  fi
done

if [[ -z "${INSTALLER}" ]]; then
  echo "Installer nicht gefunden. Erwartet u.a.:" >&2
  for c in "${INSTALLER_CANDIDATES[@]}"; do
    echo "  - ${c}" >&2
  done
  exit 1
fi

echo "[2/3] Installer ausführbar machen..."
chmod +x "${INSTALLER}"

echo "[3/3] CT-Installer starten..."
echo "Hinweis: Danach folgen interaktive Fragen (CT-ID, Domain, Secrets ...)."
echo
exec "${INSTALLER}"
