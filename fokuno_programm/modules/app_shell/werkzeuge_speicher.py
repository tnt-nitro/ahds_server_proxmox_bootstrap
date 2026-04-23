"""Sichtbare Modul-Icons in der Shell-Leiste (Ein/Aus).

Persistenz: ``~/AhDs/Shell/werkzeuge_aktiv.json``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATEI_NAME = "werkzeuge_aktiv.json"

# Alle umschaltbaren Modul-IDs (Reihenfolge = Anzeige in der Plus-Liste / Rail).
WERKZEUG_IDS: tuple[str, ...] = (
    "kalender",
    "zeitaufzeichnung",
    "krankmeldung",
    "adressbuch",
    "routinen",
    "kontakte",
    "achtsamkeit",
    "einkaufen",
    "sprachmemo",
    "schnellbild",
    "schatzkiste",
    "notizen",
)


def _pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Shell"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / _DATEI_NAME


def _standard_aktiv() -> dict[str, bool]:
    return {mid: True for mid in WERKZEUG_IDS}


def aktivitaet_laden() -> dict[str, bool]:
    """Liefert pro Modul-ID ob das Icon in der Leiste erscheinen soll."""
    roh: dict[str, bool] = _standard_aktiv()
    pf = _pfad()
    if not pf.is_file():
        return roh
    try:
        data: dict[str, Any] = json.loads(pf.read_text(encoding="utf-8"))
        gespeichert = data.get("aktiv")
        if not isinstance(gespeichert, dict):
            return roh
        for mid in WERKZEUG_IDS:
            v = gespeichert.get(mid)
            if isinstance(v, bool):
                roh[mid] = v
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return roh


def aktivitaet_speichern(aktiv: dict[str, bool]) -> None:
    """Speichert den Aktiv-Zustand (nur bekannte IDs)."""
    sauber = {mid: bool(aktiv.get(mid, True)) for mid in WERKZEUG_IDS}
    _pfad().write_text(
        json.dumps({"aktiv": sauber}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def aktivitaet_toggle(modul_id: str) -> dict[str, bool]:
    """Schaltet ein Werkzeug um und speichert."""
    if modul_id not in WERKZEUG_IDS:
        return aktivitaet_laden()
    a = aktivitaet_laden()
    a[modul_id] = not a.get(modul_id, True)
    aktivitaet_speichern(a)
    return a
