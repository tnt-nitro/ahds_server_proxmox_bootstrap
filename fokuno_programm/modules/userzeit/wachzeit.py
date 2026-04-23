"""Typische Wachzeiten des Nutzers (Eingabe/Profil – hier mit Standardwerten)."""

from __future__ import annotations

from dataclasses import dataclass

from modules.theming.farben import kalender_farben


@dataclass(frozen=True)
class PhasenFarben:
    """Farben für Wach- und Schlafphase im Kalender (später aus Nutzereinstellungen)."""

    wach_hex: str
    schlaf_hex: str


@dataclass(frozen=True)
class WachzeitProfil:
    """Wachphase von start_uhr bis ende_uhr (jeweils Stunde, Minute)."""

    start_stunde: int
    start_minute: int
    ende_stunde: int
    ende_minute: int

    @property
    def start_minuten_seit_mitternacht(self) -> int:
        return self.start_stunde * 60 + self.start_minute

    @property
    def ende_minuten_seit_mitternacht(self) -> int:
        return self.ende_stunde * 60 + self.ende_minute


def standard_wachzeit() -> WachzeitProfil:
    """Voreinstellung: 06:30–22:30 Uhr."""
    return WachzeitProfil(6, 30, 22, 30)


def standard_phasen_farben() -> PhasenFarben:
    """Standardfarben aus dem Theme (Sonne / Mond), abhängig vom Erscheinungsmodus."""
    kf = kalender_farben()
    return PhasenFarben(
        wach_hex=kf.PHASE_WACH,
        schlaf_hex=kf.PHASE_SCHLAF,
    )
