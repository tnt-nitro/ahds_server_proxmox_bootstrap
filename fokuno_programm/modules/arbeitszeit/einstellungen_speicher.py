"""Persistenz für Arbeits- und Pauseneinstellungen des Kalenders."""

from __future__ import annotations

import json
from pathlib import Path

from modules.arbeitszeit.regelprofil import RegelarbeitsProfil
from modules.pausenzeit.profil import PausenProfil, Pausenblock


def _datei_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Kalender"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "arbeits_einstellungen.json"


def _regel_als_roh(profil: RegelarbeitsProfil) -> dict[str, object]:
    tageszeiten = {
        str(k): [v[0], v[1], v[2], v[3]]
        for k, v in (profil.tageszeiten or {}).items()
    }
    return {
        "wochentage": sorted(int(w) for w in profil.wochentage),
        "start_stunde": profil.start_stunde,
        "start_minute": profil.start_minute,
        "ende_stunde": profil.ende_stunde,
        "ende_minute": profil.ende_minute,
        "tageszeiten": tageszeiten,
        "farbe_arbeit_hex": profil.farbe_arbeit_hex,
    }


def _pause_block_als_roh(block: Pausenblock) -> dict[str, int]:
    return {
        "start_stunde": block.start_stunde,
        "start_minute": block.start_minute,
        "ende_stunde": block.ende_stunde,
        "ende_minute": block.ende_minute,
    }


def _pausen_als_roh(profil: PausenProfil) -> dict[str, object]:
    return {
        "bloecke": [_pause_block_als_roh(b) for b in profil.bloecke],
        "tages_bloecke": {
            str(k): [_pause_block_als_roh(b) for b in blocks]
            for k, blocks in (profil.tages_bloecke or {}).items()
        },
        "farbe_pause_hex": profil.farbe_pause_hex,
    }


def speichern(regel: RegelarbeitsProfil, pausen: PausenProfil) -> None:
    daten = {
        "regelarbeit": _regel_als_roh(regel),
        "pausen": _pausen_als_roh(pausen),
    }
    _datei_pfad().write_text(
        json.dumps(daten, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _block_aus_roh(roh: dict[str, object]) -> Pausenblock:
    return Pausenblock(
        int(roh["start_stunde"]),
        int(roh["start_minute"]),
        int(roh["ende_stunde"]),
        int(roh["ende_minute"]),
    )


def laden(
    standard_regel: RegelarbeitsProfil,
    standard_pausen: PausenProfil,
) -> tuple[RegelarbeitsProfil, PausenProfil]:
    pfad = _datei_pfad()
    if not pfad.is_file():
        return (standard_regel, standard_pausen)
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return (standard_regel, standard_pausen)
    try:
        regel_roh = dict(roh.get("regelarbeit", {}))
        tageszeiten_roh = dict(regel_roh.get("tageszeiten", {}))
        tageszeiten: dict[int, tuple[int, int, int, int]] = {}
        for k, v in tageszeiten_roh.items():
            vals = list(v)
            if len(vals) != 4:
                continue
            tageszeiten[int(k)] = (
                int(vals[0]),
                int(vals[1]),
                int(vals[2]),
                int(vals[3]),
            )
        regel = RegelarbeitsProfil(
            wochentage=frozenset(int(v) for v in list(regel_roh.get("wochentage", []))),
            start_stunde=int(regel_roh.get("start_stunde", standard_regel.start_stunde)),
            start_minute=int(regel_roh.get("start_minute", standard_regel.start_minute)),
            ende_stunde=int(regel_roh.get("ende_stunde", standard_regel.ende_stunde)),
            ende_minute=int(regel_roh.get("ende_minute", standard_regel.ende_minute)),
            tageszeiten=tageszeiten,
            farbe_arbeit_hex=regel_roh.get("farbe_arbeit_hex"),
        )

        pausen_roh = dict(roh.get("pausen", {}))
        bloecke = tuple(_block_aus_roh(dict(b)) for b in list(pausen_roh.get("bloecke", [])))
        tages_bloecke_roh = dict(pausen_roh.get("tages_bloecke", {}))
        tages_bloecke: dict[int, tuple[Pausenblock, ...]] = {}
        for k, blocks in tages_bloecke_roh.items():
            parsed_blocks = tuple(_block_aus_roh(dict(b)) for b in list(blocks))
            tages_bloecke[int(k)] = parsed_blocks
        pausen = PausenProfil(
            bloecke=bloecke,
            tages_bloecke=tages_bloecke,
            farbe_pause_hex=pausen_roh.get("farbe_pause_hex"),
        )
    except (KeyError, TypeError, ValueError):
        return (standard_regel, standard_pausen)
    return (regel, pausen)
