# API Changelog (Staging API)

## 0.4.1

- Startseite (`/`): Texte gestrafft, Layout für Deployment-Status (Raster), dezente Typografie (`tabular-nums`, Monospace-Zeiten)
- Countdown zur nächsten Host-Prüfung: **T−** (verbleibend) und nach Fälligkeit **T+** (Überlauf in Sekunden bis zur nächsten Aktualisierung der Planzeit), ohne lange Hinweistexte
- `_SERVER_UI_VERSION` auf `ui-0.2.1`

## 0.4.0

- Startseite (`/`): Erreichbarkeits-Hintergrundprüfungen und NET/WEB/API-Pills entfernt; klarere, alltagstaugliche Texte
- Neu: `GET /status/aktuell` — JSON für Host-Update-Felder und Serverzeit (für die Startseite)
- Startseite aktualisiert Countdown und Host-Update-Infos per JavaScript (`fetch`), ohne manuelles Neuladen; Intervall über `AHDS_STARTSEITE_AKTUALISIERUNG_MS` (Standard 30 000 ms, Minimum 10 000 ms)
- `_SERVER_UI_VERSION` auf `ui-0.2.0`

## 0.3.8

- Anzeige-Fallback für Host-Update-Intervall (ohne `poll_interval_seconds` in alter JSON): Standard **300 s** (5 min), Umgebung `AHDS_UPDATE_POLL_INTERVAL_SECONDS`
- Proxmox-Deploy: Auto-Update-Standard von 15 min auf **5 min** (`ahds-native-update.timer`, `native_update_ct.sh`, `UPDATE_POLL_INTERVAL_SECONDS=300` in den Units)

## 0.3.7

- Erreichbarkeit: dritte Anzeige **Server API (:Port)** für direkten `/health`-Aufruf (Standard 8000, steuerbar mit `AHDS_API_HEALTH_PORT` / `PORT`)
- Pills umbenannt zu **Server NET (NGINX :443)** und **Server WEB (DNS+HTTPS)**; Hinweistext erklärt, warum NET rot sein kann, obwohl die Seite über :8000 lädt

## 0.3.6

- Root-Seite: automatische Erreichbarkeitsprüfung **Server NET** (HTTPS `/health` über NGINX, Loopback 127.0.0.1 mit SNI) und **Server WEB** (gleicher Hostname per DNS/TLS wie von außen)
- Hintergrundtask alle `AHDS_REACHABILITY_INTERVAL_SEC` (Standard 120), erste Prüfung nach kurzer Startverzögerung
- Pill-Farben: grün erreichbar, rot nicht erreichbar, grau ausstehend (vor erster Prüfung)

## 0.3.5

- Root-Seite: letzter Host-Lauf doppelt angezeigt (Ortszeit per `AHDS_DISPLAY_TZ`, Standard Europe/Berlin, plus UTC) — behebt die zuvor nur-UTC-Verwirrung
- `update_status.json`: Host schreibt `next_poll_at` und `poll_interval_seconds` (Intervall per `UPDATE_POLL_INTERVAL_SECONDS` am Host)
- Root-Seite: „Zeitzähler seit …“ durch **Update-Countdown** bis zur nächsten geplanten Prüfung ersetzt
- systemd: `UPDATE_POLL_INTERVAL_SECONDS` in den Update-Units (zum Timer passend)

## 0.3.4

- Hinweis im Code: Patch-Version und dieses Changelog bei sichtbaren API-/Root-UI-Änderungen pflegen
- `_SERVER_UI_VERSION` auf `ui-0.1.1`

## 0.3.3

- Root-Seite: Buttons „Aktualisieren“, „Update prüfen“, „Update installieren“ entfernt
- Stattdessen Anzeige des letzten Host-Update-Laufs (`update_status.json`) mit UTC-Zeitstempel und Live-Zähler (Sekunden seit letztem Lauf)
- Endpunkte `/update/status` und `/update/request` entfernt

## 0.3.2

- Klarere Rückmeldung zu `/update/request`: Hinweis auf Proxmox-Host-Watcher bzw. manuelles Skript
- Proxmox-Doku: Watcher-Timer (`ahds-native-update-on-request`) bei vorhandener `update_request.json` im CT

## 0.3.1

- Root-Seite sprachlich bereinigt (kein „Title“ mehr in der Überschrift)
- Server-Build-Anzeige auf bekannte Build-Bezeichnungen vereinheitlicht
  (`Development Build`, `Staging Build`, `Production Build`)
- Unnötige Unterzeile auf der Root-Seite entfernt

## 0.3.0

- Auth-Basis mit Access/Refresh-Token, Logout/Refresh
- Rollenmodell (`user`/`admin`) mit Admin-Endpunkten
- Passwort-Reset-Flow (request/confirm)
- Login-Bruteforce-Schutz (Fehlversuche + temporäre Sperre)
- Audit-Logging + Admin-Audit-API mit Filter/Pagination
- Header für Pagination (`X-Total-Count`, `Link`)
- API-Versionsmetadaten (`/v1/meta/version`, `X-API-Major`, `X-API-Release`)
- Client-Kompatibilitätsheader für `v1` (`X-Client-Api-Major: v1`, sonst `426`)
- Deprecation-Mechanik (`Deprecation`, `Sunset`, `Link rel="successor-version"`)
- Deprecation-Meta-Endpunkt (`/v1/meta/deprecations`) und Altpfad `/v1/admin/logs` → `/v1/admin/audit-logs`

## Breaking-Change-Regel

- Solange Endpunkte unter `v1` bleiben, werden keine bewusst inkompatiblen Payload-/Semantik-Änderungen eingeführt.
- Für echte Breaking Changes wird ein neuer Major-Pfad (`v2`, ...) eingeführt.
