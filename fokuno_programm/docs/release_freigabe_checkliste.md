# Release-Freigabe-Checkliste (Staging)

Diese Liste ist der Mindeststandard, bevor ein Test-Release an externe Tester geht.

## 1) Technische Freigabe

- CI ist grün (`.github/workflows/ci.yml`).
- Release-Workflow ist grün für den Tag (`.github/workflows/release.yml`).
- Staging-API antwortet auf `GET /health` und `GET /ready` stabil.
- Migrationen laufen fehlerfrei durch.
- Proxmox-Staging wurde nach Anleitung geprüft (`fokuno_proxmox/deploy/proxmox/README.md`).

## 2) Versions- und Kompatibilitätsprüfung

- Release-Tag gesetzt (z. B. `v0.x.y-rcN`).
- `GET /v1/meta/version` liefert erwarteten Stand.
- Header `X-API-Major`, `X-API-Release` sind korrekt.
- Clients senden `X-Client-Api-Major: v1`.

## 3) Sicherheits-/Betriebsprüfung

- `API_TOKEN_SECRET` ist gesetzt (nicht Default).
- `POSTGRES_PASSWORD` ist stark gesetzt.
- `ADMIN_EMAIL` korrekt.
- Login-Schutz (`LOGIN_MAX_FEHLVERSUCHE`, `LOGIN_SPERRE_SEKUNDEN`) plausibel.
- Reset-TTL (`RESET_TOKEN_TTL_SEKUNDEN`) plausibel.
- Backup-Job aktiv (mindestens manuell getestet, ideal: systemd timer aktiv).

## 4) Testumfang

- Auth-Flow getestet (Register/Login/Refresh/Logout).
- Passwort-Reset getestet.
- Admin-Endpunkte getestet (Users + Audit-Logs).
- Mindestens 1 End-to-End-Eventfluss getestet (`/v1/events`).

## 5) Externe Tester-Freigabe

- Tester erhalten genau den Release-Tag/Build-Link.
- Release-Regeln beachtet (siehe `docs/release_policy.md`).
- Feedback läuft über GitHub-Issue-Template:
  - `.github/ISSUE_TEMPLATE/test-feedback.yml`
- Rückmeldung enthält Plattform + Release-Tag + Repro-Schritte.

## 6) Abbruchkriterien

- Bei kritischen Fehlern: kein nächster Freigabe-Tag.
- Hotfix nur über neuen Tag, nie ungeplant aus `main`.
