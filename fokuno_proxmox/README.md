# fokuno_proxmox

Dieser Ordner ist der zentrale Einstiegspunkt für alles rund um Proxmox/Server-Betrieb.

## Ziel

- Wenn du etwas zum Proxmox-Thema suchst, findest du es hier.
- Bootstrap und Installations-Einstieg zeigen auf diesen Ordner.
- Alle Proxmox-/Server-Deploy-Dateien liegen unter `fokuno_proxmox/deploy`.

## Wichtige Dateien

- `install_proxmox_ct_nodocker.sh`  
  Erstellt einen CT und installiert AhDs nativ im CT.
- `install_native_nodocker.sh`  
  Native Installation ohne CT-Erstellung (Spezialfall).
- `deploy/proxmox/`  
  Betriebs- und Installationsskripte für Proxmox.
- `deploy/staging_api/`  
  API-Code, Migrationen und Runtime-Abhängigkeiten für den Server.
