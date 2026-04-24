# API Changelog (Staging API)

## 0.3.2

- Klarere Rückmeldung zu `/update/request`: Hinweis auf Proxmox-Host-Watcher bzw. manuelles Skript
- Proxmox-Doku: Watcher-Timer (`ahds-native-update-on-request`) für nahezu sofortige Reaktion auf den Browser-Button

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
