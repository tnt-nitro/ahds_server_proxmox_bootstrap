# AhDs Proxmox Bootstrap

Ein öffentlicher Bootstrap-Installer für Proxmox, der das private AhDs-Projekt lädt und den CT-Installer startet.

## One-Liner

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/tnt-nitro/ahds-proxmox-bootstrap/main/install-ahds-ct.sh)"
```

## Was das Script macht

1. Klont oder aktualisiert das private Repo `tnt-nitro/fokuno` nach `/opt/ahds`
2. Startet `fokuno_proxmox/install_proxmox_ct_nodocker.sh`
3. Führt dich durch die CT-Erstellung und native Installation ohne Docker

## Voraussetzungen

- Proxmox-Host als `root`
- SSH-Zugriff auf das private Repo (`git@github.com:tnt-nitro/fokuno.git`)
  - z. B. per Deploy Key
- Internetzugriff für Paketinstallation und LXC-Template-Download
