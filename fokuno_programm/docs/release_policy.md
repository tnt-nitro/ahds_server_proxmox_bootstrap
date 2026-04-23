# Release Policy (AhDs Staging)

Diese Regeln sichern, dass Tester nur freigegebene stabile Stände sehen.

## 1) Branch-Rollen

- `main`  
  Laufende Entwicklung (intern). Keine direkte externe Testfreigabe.

- `release/*`  
  Stabilisierung vor Freigabe (optional, wenn größerer Testumfang nötig ist).

- `hotfix/*`  
  Schnelle Fehlerbehebung für bereits freigegebenen Stand.

## 2) Tag-Regel (Freigabeanker)

- Externe Testfreigaben laufen über Tags (`vX.Y.Z-rcN`, später `vX.Y.Z`).
- Nur Tag-basierte Workflows dürfen den Testerkanal bedienen.
- Kein ungeplanter Teststand direkt aus `main`.

## 3) Mindestablauf pro Testfreigabe

1. Entwicklungsstand in `main` ist technisch stabil.
2. Optional: `release/*`-Branch zur letzten Stabilisierung.
3. Tag setzen (`v0.x.y-rcN`) und pushen.
4. Release-Workflow muss grün sein.
5. Freigabe an Tester inkl. Tag-Hinweis + Changelog.
6. Feedback über Issue-Template erfassen.

## 4) Hotfix-Ablauf

1. `hotfix/*` aus letztem freigegebenen Tag ableiten.
2. Fix einbauen, testen, neuen Tag (`v0.x.y-rcN+1` oder `v0.x.(y+1)-rc1`) setzen.
3. Tester auf neuen Tag umstellen.

## 5) Schutzregeln (GitHub, empfohlen)

- Pull-Request-Pflicht für `main`.
- Direktes Pushen auf `main` vermeiden.
- Erforderliche Statuschecks:
  - `CI`
  - `Release` (für Tag-Freigaben)
- Optional: mind. 1 Review vor Merge.

## 6) Nicht erlaubt

- Tester-Builds ohne Tag.
- Änderungen direkt auf Staging-System ohne nachvollziehbaren Commit/Tag.
- Manuelle „Schattenstände“, die nicht zur Git-Historie passen.
