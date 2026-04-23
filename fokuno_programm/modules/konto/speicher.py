"""Lokale Kontodaten: Benutzer mit Passwort-Hash (PBKDF2), Datei unter data/konto/."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ITERATIONEN = 100_000


def _programm_stamm() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _benutzer_datei() -> Path:
    return _programm_stamm() / "data" / "konto" / "benutzer.json"


@dataclass(frozen=True)
class Benutzer:
    """Öffentliche Kontoinformationen (ohne Passwortdaten)."""

    id: str
    name: str
    email: str


def _hash_neu(passwort: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", passwort.encode("utf-8"), salt, _ITERATIONEN
    )
    return salt.hex(), dk.hex()


def _hash_ok(passwort: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        erw = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", passwort.encode("utf-8"), salt, _ITERATIONEN
    )
    return secrets.compare_digest(dk, erw)


def _nico_seed_eintrag() -> dict[str, Any]:
    s, h = _hash_neu("x")
    return {
        "id": "ahds-seed-nico",
        "name": "Nico",
        "email": "tnt-nitro@web.de",
        "salt_hex": s,
        "hash_hex": h,
    }


def _datei_laden_roh() -> dict[str, Any]:
    pfad = _benutzer_datei()
    if not pfad.exists():
        return {"users": []}
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"users": []}


def _datei_schreiben(data: dict[str, Any]) -> None:
    pfad = _benutzer_datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def stammdaten_sicherstellen() -> None:
    """Legt die Datei an und stellt den Startbenutzer Nico sicher (ohne bestehende zu löschen)."""
    pfad = _benutzer_datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    data = _datei_laden_roh()
    users: list[dict[str, Any]] = list(data.get("users", []))
    if not users:
        _datei_schreiben({"users": [_nico_seed_eintrag()]})
        return
    namen = {str(u.get("name", "")) for u in users}
    if "Nico" not in namen:
        users.append(_nico_seed_eintrag())
        _datei_schreiben({"users": users})


def anmelden(name: str, passwort: str) -> Benutzer | None:
    """Prüft Name und Passwort; liefert Benutzer oder None."""
    stammdaten_sicherstellen()
    roh = _datei_laden_roh()
    such = name.strip()
    for u in roh.get("users", []):
        if str(u.get("name", "")) != such:
            continue
        salt_hex = u.get("salt_hex", "")
        hash_hex = u.get("hash_hex", "")
        if not salt_hex or not hash_hex:
            continue
        if _hash_ok(passwort, str(salt_hex), str(hash_hex)):
            return Benutzer(
                id=str(u.get("id", "")),
                name=str(u.get("name", "")),
                email=str(u.get("email", "")),
            )
    return None
