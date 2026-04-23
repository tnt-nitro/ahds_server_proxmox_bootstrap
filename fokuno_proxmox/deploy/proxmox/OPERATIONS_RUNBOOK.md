# AhDs Staging Operations Runbook

Dieses Runbook beschreibt den täglichen Betrieb der Staging-Umgebung auf Proxmox.

## Scope

- Umgebung: `staging`
- Stack: `caddy_staging`, `api_staging`, `postgres_staging`
- Ordner: `fokuno_proxmox/deploy/proxmox`

## 1) Standardbefehle

Im Zielordner:

```bash
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
```

### Stack starten / stoppen

```bash
docker compose --env-file .env -f staging-compose.proxmox.yml up -d --build
docker compose --env-file .env -f staging-compose.proxmox.yml down
```

### Status / Logs

```bash
docker compose --env-file .env -f staging-compose.proxmox.yml ps
docker compose --env-file .env -f staging-compose.proxmox.yml logs --tail=200 api_staging
docker compose --env-file .env -f staging-compose.proxmox.yml logs --tail=200 caddy_staging
docker compose --env-file .env -f staging-compose.proxmox.yml logs --tail=200 postgres_staging
```

### Reproduzierbares Update

```bash
./deploy_update.sh
```

### Healthcheck

```bash
./healthcheck_proxmox.sh
```

## 2) Backup / Restore

### Backup

```bash
./backup_db.sh
```

- Ergebnis liegt unter `./backups/ahds-staging-YYYYmmdd-HHMMSS.sql.gz`

### Restore (Achtung: überschreibt DB)

```bash
./restore_db.sh ./backups/ahds-staging-YYYYmmdd-HHMMSS.sql.gz
```

## 3) Systemd-Betrieb

### Erwartete Units

- `ahds-staging.service`
- `ahds-staging-backup.service`
- `ahds-staging-backup.timer`

### Prüfen

```bash
systemctl status ahds-staging.service
systemctl status ahds-staging-backup.timer
systemctl list-timers | grep ahds-staging
```

### Neu laden / aktivieren

```bash
systemctl daemon-reload
systemctl enable --now ahds-staging.service
systemctl enable --now ahds-staging-backup.timer
```

## 4) Incident-Checkliste (Kurz)

1. `docker compose ... ps` prüfen: laufen alle Container?
2. `./healthcheck_proxmox.sh` ausführen.
3. Wenn `/ready` fehlschlägt:
   - Postgres-Logs prüfen
   - DB-Verbindung/Secrets in `.env` prüfen
4. Wenn TLS/Domain fehlschlägt:
   - `caddy_staging` Logs prüfen
   - DNS/Ports 80+443 prüfen
5. Wenn Auth/API fehlschlägt:
   - `api_staging` Logs prüfen
   - `API_TOKEN_SECRET` / `ADMIN_EMAIL` / Login-Limits prüfen

## 5) Rollback-Strategie (einfach)

Wenn ein Update fehlschlägt:

1. Letztes funktionierendes Git-Commit/Tag auschecken.
2. Stack neu bauen/starten:

```bash
./deploy_update.sh
```

1. Falls Datenproblem:
   - aktuelles Backup sichern
   - letztes funktionierendes Backup mit `restore_db.sh` einspielen

## 6) Betriebsregeln

- Keine geheimen Werte ins Repo (`.env` bleibt lokal).
- Vor externer Testfreigabe immer:
  - CI/Release grün
  - `./healthcheck_proxmox.sh` erfolgreich
  - aktuelles Backup vorhanden
