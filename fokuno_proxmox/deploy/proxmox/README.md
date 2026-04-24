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
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
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

## Warum /admin evtl. nicht sichtbar war

Wenn die Browser-Seite nicht den neuesten Stand zeigt (z. B. `/admin` fehlt), läuft meist noch alter Code im CT.
Dann ausführen:

```bash
cd /opt/ahds
git pull --ff-only origin main
pct exec 113 -- systemctl restart ahds-staging-api
```

Danach testen:

```bash
curl -I http://192.168.178.87:8000/
curl -I http://192.168.178.87:8000/admin
```

## Automatisches Update (ohne Docker)

Es gibt jetzt ein Update-Skript, das neue Commits holt und in den CT einspielt:

```bash
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
chmod +x native_update_ct.sh
CTID=113 ./native_update_ct.sh
```

Die Startseite (`/`) zeigt den **letzten Host-Update-Lauf** (Ortszeit z. B. `Europe/Berlin` plus UTC), das **konfigurierte Prüf-Intervall**, die **nächste geplante Prüfzeit** (`next_poll_at`, aus dem Host-Skript) und einen **Update-Countdown** (Restzeit bis `next_poll_at`). Diese Angaben aktualisieren sich im Browser von selbst (siehe `AHDS_STARTSEITE_AKTUALISIERUNG_MS` in `fokuno_proxmox/deploy/staging_api/README.md`). Datenquelle: `/opt/ahds-native/data/update_status.json` im CT (schreibt `native_update_ct.sh`).

- **Ortszeit in der API:** Umgebungsvariable `AHDS_DISPLAY_TZ` (Standard `Europe/Berlin`) im systemd-Service `ahds-staging-api` setzen, falls du eine andere Zone brauchst.
- **Intervall-Fallback ohne `next_poll_at` in alter JSON:** `AHDS_UPDATE_POLL_INTERVAL_SECONDS` im CT (Standard `300`) — nach dem nächsten Host-Lauf steht `next_poll_at` zuverlässig in der Datei.
- **Host:** Variable `UPDATE_POLL_INTERVAL_SECONDS` muss zum systemd-Timer passen (z. B. `300` bei `OnUnitActiveSec=5min`); siehe `ahds-native-update.service`.

### Optional: Host reagiert auf Datei `update_request.json` im CT (Watcher)

Wenn du z. B. per Skript im CT die Datei `/opt/ahds-native/data/update_request.json` anlegst, kann der Host sie per Timer erkennen und `native_update_ct.sh` starten (ca. alle 45 Sekunden):

```bash
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
chmod +x native_update_ct_on_request.sh
cp systemd/ahds-native-update-on-request.service /etc/systemd/system/
cp systemd/ahds-native-update-on-request.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ahds-native-update-on-request.timer
```

Wenn die CT-ID nicht **113** ist, in beiden Unit-Dateien `Environment=CTID=113` anpassen, dann `daemon-reload` und Timer neu starten.

Prüfen:

```bash
systemctl status ahds-native-update-on-request.timer
journalctl -u ahds-native-update-on-request.service -n 40 --no-pager
```

### Auto-Update per systemd-Timer (alle 5 Minuten, optional)

Periodisches Einspielen neuer Commits **ohne** Klick im Browser:

```bash
cp systemd/ahds-native-update.service /etc/systemd/system/
cp systemd/ahds-native-update.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ahds-native-update.timer
```

**Bereits eingerichtet und nur Intervall/Units aktualisieren:** geänderte `ahds-native-update.service` und `ahds-native-update.timer` erneut nach `/etc/systemd/system/` kopieren, dann `systemctl daemon-reload` und `systemctl restart ahds-native-update.timer`.

Prüfen:

```bash
systemctl status ahds-native-update.timer
systemctl list-timers | grep ahds-native-update
journalctl -u ahds-native-update.service -n 80 --no-pager
```

## Schnellstart ohne Docker (empfohlen für deinen Fall)

Wenn du **kein Docker** auf dem Proxmox-Host willst, nutze den nativen Installer:

```bash
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
chmod +x install_native_nodocker.sh
./install_native_nodocker.sh
```

Das Skript richtet automatisch ein:

- PostgreSQL lokal
- FastAPI als systemd-Service (`ahds-staging-api.service`)
- NGINX Reverse Proxy
- TLS mit Certbot (**`--quiet`**, bei Fehler nur ein **kurzer Auszug** aus `letsencrypt.log`)
- optional DuckDNS-Cron (wenn Token eingegeben wird)
- **`STAGING_DOMAIN`** und **`TLS_EMAIL`** in `/opt/ahds-native/.env` (für NGINX, TLS und öffentliche Adresse)

**NGINX kurz selbst testen** (nach Installation oder bei Problemen):

```bash
cd /opt/ahds/fokuno_proxmox/deploy/proxmox
chmod +x nginx_staging_preflight.sh
./nginx_staging_preflight.sh
```

Details und Nachziehen der `.env` bei alten CTs: [`OPERATIONS_RUNBOOK.md`](./OPERATIONS_RUNBOOK.md) Abschnitt **7**.

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
cd fokuno_proxmox/deploy/proxmox
```

### Alternative: One-Command-Installation direkt von GitHub

Vom PC aus per SSH auf dem Proxmox-Host starten:

```bash
ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_proxmox/deploy/proxmox/install_from_github.sh)\""
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
ssh root@<PROXMOX_IP> "bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_proxmox/deploy/proxmox/install_from_github.sh) --dry-run\""

# Installieren ohne systemd-Aktivierung
ssh root@<PROXMOX_IP> "STAGING_DOMAIN=staging.example.org TLS_EMAIL=admin@example.org POSTGRES_PASSWORD='<STRONG>' API_TOKEN_SECRET='<VERY_STRONG>' ADMIN_EMAIL='admin@example.org' bash -lc \"\$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/fokuno/main/fokuno_proxmox/deploy/proxmox/install_from_github.sh) --no-systemd\""
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
   `/opt/ahds/fokuno_proxmox/deploy/proxmox`

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
