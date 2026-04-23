# Proxmox Staging Setup

Dieses Setup ist die Brücke von lokaler Entwicklung zu einem dauerhaft laufenden Staging-System auf Proxmox.

Für den täglichen Betrieb siehe auch: [`OPERATIONS_RUNBOOK.md`](./OPERATIONS_RUNBOOK.md)
Für den ersten Live-Start siehe: [`GO_LIVE_PROXMOX.md`](./GO_LIVE_PROXMOX.md)

## Ziel

- API + DB laufen unabhängig vom Entwicklungs-PC.
- Zugriff über feste Domain mit TLS.
- Backups der Staging-Datenbank sind reproduzierbar.

## Schnellstart mit eigenem Proxmox-CT (neu)

Wenn du eine sichtbare, getrennte Instanz mit eigener CT-ID willst:

```bash
cd /opt/ahds/fokuno_programm/deploy/proxmox
chmod +x install_proxmox_ct_nodocker.sh
./install_proxmox_ct_nodocker.sh
```

Das Skript:

- erstellt automatisch einen LXC-CT
- zeigt dir CT-ID/Hostname/IP
- installiert AhDs nativ im CT (ohne Docker)
- erlaubt später einfaches Löschen über `pct destroy <CTID> --purge 1`

Wichtig:

- Für TLS muss die Domain auf die CT-IP zeigen (oder Portforwarding auf CT-IP).

### Öffentlicher Bootstrap-One-Liner

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/ahds-proxmox-bootstrap/main/install-ahds-ct.sh)"
```

Damit wird das private Repo unter `/opt/ahds` aktualisiert/geklont und anschließend der CT-Installer gestartet.

## Schnellstart ohne Docker (empfohlen für deinen Fall)

Wenn du **kein Docker** auf dem Proxmox-Host willst, nutze den nativen Installer:

```bash
cd /opt/ahds/fokuno_programm/deploy/proxmox
chmod +x install_native_nodocker.sh
./install_native_nodocker.sh
```

Das Skript richtet automatisch ein:

- PostgreSQL lokal
- FastAPI als systemd-Service (`ahds-staging-api.service`)
- NGINX Reverse Proxy
- TLS mit Certbot
- optional DuckDNS-Cron (wenn Token eingegeben wird)

Wichtig:

- Dieses Skript installiert **nativ auf dem aktuellen System**.
- Es erstellt **keinen** Proxmox-CT automatisch.

Danach testen:

```bash
curl -I https://<DEINE_DOMAIN>/health
curl -I https://<DEINE_DOMAIN>/ready
curl -I https://<DEINE_DOMAIN>/v1/meta/version
```

## Voraussetzungen

- Docker + Compose auf der Proxmox-VM/LXC installiert
- DNS-Eintrag für `STAGING_DOMAIN` zeigt auf den Host
- Ports 80/443 erreichbar

## Inbetriebnahme

1. In diesen Ordner wechseln:

```bash
cd fokuno_programm/deploy/proxmox
```

### Alternative: One-Command-Installation direkt von GitHub

Vom PC aus per SSH auf dem Proxmox-Host starten:

```bash
ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_programm/deploy/proxmox/install_from_github.sh)\""
```

Das Skript:

- klont/aktualisiert das Repo unter `/opt/ahds`
- erstellt/aktualisiert `.env`
- führt Preflight + Deploy aus
- richtet optional systemd ein
- unterstützt `--help`, `--dry-run`, `--no-systemd`

Beispiele:

```bash
# Nur prüfen, keine Änderungen
ssh root@<PROXMOX_IP> "bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_programm/deploy/proxmox/install_from_github.sh) --dry-run\""

# Installieren ohne systemd-Aktivierung
ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_programm/deploy/proxmox/install_from_github.sh) --no-systemd\""
```

Optional vor dem ersten Start:

```bash
chmod +x preflight_proxmox.sh
./preflight_proxmox.sh
```

1. Env-Datei anlegen:

```bash
cp .env.example .env
```

1. `.env` anpassen:

- `STAGING_DOMAIN`
- `TLS_EMAIL`
- `POSTGRES_PASSWORD`
- `API_TOKEN_SECRET`
- optional `ADMIN_EMAIL` und Login/Reset-Limits

1. Stack starten:

```bash
docker compose --env-file .env -f staging-compose.proxmox.yml up -d --build
```

1. Prüfen:

- `https://<STAGING_DOMAIN>/health`
- `https://<STAGING_DOMAIN>/ready`
- `https://<STAGING_DOMAIN>/v1/meta/version`

## Update-Workflow

Nach neuen Commits/Tags:

```bash
docker compose --env-file .env -f staging-compose.proxmox.yml pull || true
docker compose --env-file .env -f staging-compose.proxmox.yml up -d --build
```

Oder als Ein-Befehl-Skript:

```bash
chmod +x deploy_update.sh
./deploy_update.sh
```

## Backup

DB-Backup ausführen:

```bash
chmod +x backup_db.sh
./backup_db.sh
```

Das Backup landet unter `./backups/`.

## Restore

Backup zurückspielen:

```bash
chmod +x restore_db.sh
./restore_db.sh ./backups/ahds-staging-YYYYmmdd-HHMMSS.sql.gz
```

Hinweis: Restore überschreibt die aktuelle Staging-DB.

## Healthcheck

Schneller Live-Check (Container + API + Meta):

```bash
chmod +x healthcheck_proxmox.sh
./healthcheck_proxmox.sh
```

## Systemd (Autostart + Backup-Timer)

Im Ordner `systemd/` liegen Unit-Dateien für:

- `ahds-staging.service` (Stack autostarten/stoppen)
- `ahds-staging-backup.service` (ein Backup-Lauf)
- `ahds-staging-backup.timer` (nächtlich 03:30)

### Installation auf Proxmox (als root)

1. Pfad prüfen/anpassen  
   Die Unit-Dateien nutzen standardmäßig:
   `/opt/ahds/fokuno_programm/deploy/proxmox`

1. Units kopieren:

```bash
cp systemd/ahds-staging.service /etc/systemd/system/
cp systemd/ahds-staging-backup.service /etc/systemd/system/
cp systemd/ahds-staging-backup.timer /etc/systemd/system/
```

1. Aktivieren:

```bash
systemctl daemon-reload
systemctl enable --now ahds-staging.service
systemctl enable --now ahds-staging-backup.timer
```

1. Status prüfen:

```bash
systemctl status ahds-staging.service
systemctl status ahds-staging-backup.timer
systemctl list-timers | grep ahds-staging
```

Empfehlung: nach jedem Deploy zusätzlich `./healthcheck_proxmox.sh` ausführen.
