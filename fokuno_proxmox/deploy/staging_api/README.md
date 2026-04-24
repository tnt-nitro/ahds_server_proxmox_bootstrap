# Staging API (AhDs)

Dieses Verzeichnis enthält die minimale Staging-API mit Auth, Rollen, Events und Audit-Log.

## API-Versionierung

- Major-Pfad: aktuell `v1`
- Metadaten-Endpunkt: `GET /v1/meta/version`
- Deprecation-Übersicht: `GET /v1/meta/deprecations`
- Response-Header auf allen Endpunkten:
  - `X-API-Major` (z. B. `v1`)
  - `X-API-Release` (aktuelle API-Release-Version)
- Client-Pflichtheader für `v1`-Endpunkte (außer `/v1/meta/version`):
  - `X-Client-Api-Major: v1`
  - Bei fehlendem/falschem Header: HTTP `426`
- Kompatibilitätsregel: innerhalb einer Major-Version keine Breaking Changes ohne neuen Major-Pfad.

## Start lokal (über Compose im `deploy`-Ordner)

1. `staging.env.example` nach `.env` kopieren
2. Passwörter/Secrets anpassen (`POSTGRES_PASSWORD`, `API_TOKEN_SECRET`)
3. Starten:

```powershell
cd "..\"
docker compose -f staging-compose.yml up -d
```

## Wichtige Endpunkte

- `GET /` – AhDs Browser-Startseite (Host-Update-Infos mit Auto-Aktualisierung, Login)
- `GET /status/aktuell` – JSON für die Startseite (Serverzeit, Host-Update aus `update_status.json`)
- `GET /admin` – Admin-Seite für Runtime-Werte (.env)
- `GET /health` – Liveness
- `GET /ready` – DB-Readiness
- `GET /v1/meta/version`
- `GET /v1/meta/deprecations`
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`
- `POST /v1/auth/logout`
- `POST /v1/auth/password-reset/request`
- `POST /v1/auth/password-reset/confirm`
- `GET /v1/users/me`
- `GET /v1/events`
- `POST /v1/events`
- `GET /v1/admin/users` (nur `admin`)
- `GET /v1/admin/audit-logs` (nur `admin`)
- `GET /v1/admin/logs` (deprecated Alias auf Audit-Logs)

## Startseite: Auto-Aktualisierung (`/`)

Die HTML-Startseite lädt Host-Update-Daten und den Countdown per `fetch` von **`GET /status/aktuell`** nach, ohne dass du die Seite neu laden musst.

- **`AHDS_STARTSEITE_AKTUALISIERUNG_MS`**: Abstand zwischen den Abrufen im Browser (Standard **30000**, Minimum **10000**). Setzen im systemd-Service `ahds-staging-api` (Umgebungsvariablen der Unit), danach Dienst neu starten.

## Admin-Seite (temporär)

- Login per HTTP Basic Auth:
  - User: `Admin`
  - Passwort: `x`
- Über `/admin` kannst du Installationswerte nachträglich pflegen
  (`STAGING_DOMAIN`, `TLS_EMAIL`, `ADMIN_EMAIL`, Limits, optionale Secrets).
- Hinweis: Nach Änderungen an Secrets/DB-Werten den Service neu starten:
  `systemctl restart ahds-staging-api`

## Audit-Logs: Filter + Pagination

`GET /v1/admin/audit-logs`

Query-Parameter:

- `limit` (1..500, default `100`)
- `offset` (>= 0)
- `event` (exakter Event-Name)
- `ok` (`true`/`false`)
- `since` (ISO-Datetime, inkl. Zeitzone)
- `until` (ISO-Datetime, inkl. Zeitzone)

Response-Header:

- `X-Total-Count`: Gesamtanzahl für den aktuellen Filter (ohne Pagination)
- `Link`: enthält `rel="next"` und/oder `rel="prev"` falls weitere Seiten existieren

### Beispiel

```bash
curl -i \
  -H "authorization: Bearer <ADMIN_ACCESS_TOKEN>" \
  "http://127.0.0.1:8000/v1/admin/audit-logs?limit=20&offset=0&event=auth.register&ok=true"
```

Im Header siehst du dann z. B.:

- `X-Total-Count: 42`
- `Link: <http://...offset=20...>; rel="next"`

## Changelog

Der API-Änderungsverlauf steht in [`CHANGELOG.md`](./CHANGELOG.md).

## Testerprozess

- Feedback-Template: `/.github/ISSUE_TEMPLATE/test-feedback.yml`
- Freigabe-Checkliste: [`../docs/release_freigabe_checkliste.md`](../docs/release_freigabe_checkliste.md)

## Deprecation-Header

Veraltete Endpunkte liefern zusätzlich:

- `Deprecation: true`
- `Sunset: <HTTP-Datum>`
- `Link: <...>; rel="successor-version"`

Aktuell ist `/v1/admin/logs` als Altpfad markiert; Nachfolger ist `/v1/admin/audit-logs`.
