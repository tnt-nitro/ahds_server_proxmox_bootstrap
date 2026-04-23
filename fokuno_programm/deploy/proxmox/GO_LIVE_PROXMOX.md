# Proxmox Go-Live Checkliste (Staging)

Diese Liste führt dich einmal sauber durch den ersten Live-Betrieb auf Proxmox.

## 0) Vorbereitung am Host

```bash
cd /opt/ahds/fokuno_programm/deploy/proxmox
cp .env.example .env
```

`.env` setzen:

- `STAGING_DOMAIN`
- `TLS_EMAIL`
- `POSTGRES_PASSWORD` (stark)
- `API_TOKEN_SECRET` (sehr stark)
- `ADMIN_EMAIL`

Alternative (Automatik via GitHub-Skript, vom PC aus):

```bash
ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_programm/deploy/proxmox/install_from_github.sh)\""
```

Optional zuerst als Trockenlauf:

```bash
ssh root@<PROXMOX_IP> "bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_programm/deploy/proxmox/install_from_github.sh) --dry-run\""
```

## 1) Preflight

```bash
chmod +x preflight_proxmox.sh
./preflight_proxmox.sh
```

Wenn Warnungen kommen, entscheiden:

- **Blocker** (fehlende Variablen, kaputte Compose-Config) -> zuerst beheben.
- **Hinweise** (Ports lauschen noch nicht) -> vor Start normal.

## 2) Erster Live-Deploy

```bash
chmod +x deploy_update.sh
./deploy_update.sh
```

## 3) Live-Healthcheck

```bash
chmod +x healthcheck_proxmox.sh
./healthcheck_proxmox.sh
```

Zusätzlich manuell im Browser:

- `https://<STAGING_DOMAIN>/health`
- `https://<STAGING_DOMAIN>/ready`
- `https://<STAGING_DOMAIN>/v1/meta/version`

## 4) Systemd aktivieren (Dauerbetrieb)

```bash
cp systemd/ahds-staging.service /etc/systemd/system/
cp systemd/ahds-staging-backup.service /etc/systemd/system/
cp systemd/ahds-staging-backup.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now ahds-staging.service
systemctl enable --now ahds-staging-backup.timer
```

Prüfen:

```bash
systemctl status ahds-staging.service
systemctl status ahds-staging-backup.timer
systemctl list-timers | grep ahds-staging
```

## 5) Erstes Backup (Pflicht)

```bash
chmod +x backup_db.sh
./backup_db.sh
ls -lh backups/
```

## 6) Externer Teststart

1. Release-Tag freigeben (siehe `docs/release_policy.md`).
1. Tester-Link + Tag kommunizieren.
1. Feedback nur über GitHub-Template (`.github/ISSUE_TEMPLATE/test-feedback.yml`).

## 7) Fallback bei Problemen

1. Stack-Status prüfen:

```bash
docker compose --env-file .env -f staging-compose.proxmox.yml ps
docker compose --env-file .env -f staging-compose.proxmox.yml logs --tail=200 api_staging
```

2. Bei Datenproblem:

```bash
./restore_db.sh ./backups/<backup-datei>.sql.gz
```

3. Danach wieder:

```bash
./healthcheck_proxmox.sh
```
