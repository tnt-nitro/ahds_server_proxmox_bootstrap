# _gesperrt

Dieser Ordner ist fuer technische Notizen und Konfigurationen, die nicht oeffentlich erreichbar sein sollen.

## Punkt 1: `/admin` nur intern oder per VPN

Ziel:
- `/admin` darf aus dem Heimnetz erreichbar sein.
- Aus dem oeffentlichen Internet soll `/admin` gesperrt sein (`403 Forbidden`).
- Zugriff per VPN ist erlaubt, wenn das VPN-Subnetz zusaetzlich freigegeben wird.

## Nginx Proxy Manager (Custom Location)

Im NPM Proxy Host:
- `Custom Locations` -> `Location`: `/admin`
- `Scheme`: `http`
- `Forward Hostname / IP`: `192.168.178.87`
- `Forward Port`: `80`

Im Zahnradfeld (Custom Nginx Configuration) nur:

```nginx
allow 127.0.0.1;
allow 192.168.178.0/24;
# Optional: VPN-Subnetz freigeben, Beispiel:
# allow 10.0.0.0/24;
deny all;
```

Wichtig:
- Kein eigener `location { ... }`-Block im Feld eintragen.
- Kein `proxy_pass` im Feld eintragen (das macht NPM ueber die Eingabefelder).

## Test

1. Heimnetz (WLAN/LAN):
   - `https://<domain>/admin` -> erreichbar
2. Mobilfunk (WLAN aus):
   - `https://<domain>/admin` -> `403 Forbidden`

## Hinweis zu `/_gesperrt`

Wenn auch ein URL-Pfad `/_gesperrt` von extern gesperrt werden soll, in NPM eine weitere Custom Location `/_gesperrt` mit denselben `allow/deny`-Regeln anlegen.
