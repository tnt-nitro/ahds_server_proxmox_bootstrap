"""Regelmäßige Arbeitszeit (ohne Schichtmodelle). Ausbau später: Schicht, Nebenjob, Gleitzeit, Bereitschaft."""

from __future__ import annotations

from dataclasses import dataclass

import datetime as dt

from modules.theming.farben import kalender_farben


def alle_wochentage() -> frozenset[int]:
    """Mo–So (`datetime.weekday`: Mo = 0 … So = 6)."""
    return frozenset(range(7))


def werkwoch_wochentage() -> frozenset[int]:
    """Mo–Fr (`datetime.weekday`: 0 … 4)."""
    return frozenset(range(5))


@dataclass(frozen=True)
class RegelarbeitsProfil:
    """Einfaches Arbeitsfenster an ausgewählten Wochentagen (eine Spanne pro Tag)."""

    wochentage: frozenset[int]
    start_stunde: int
    start_minute: int
    ende_stunde: int
    ende_minute: int
    #: Optional: tagesgenaue Arbeitszeiten pro Wochentag (0=Mo ... 6=So).
    #: Wertformat je Tag: (start_stunde, start_minute, ende_stunde, ende_minute).
    tageszeiten: dict[int, tuple[int, int, int, int]] | None = None
    farbe_arbeit_hex: str | None = None

    def ist_arbeitstag(self, tag: dt.date) -> bool:
        return self.arbeitszeit_fuer_tag(tag) is not None

    def arbeitszeit_fuer_wochentag(self, wochentag: int) -> tuple[int, int] | None:
        """Start/Ende in Minuten seit Mitternacht für einen Wochentag."""
        if self.tageszeiten is not None and wochentag in self.tageszeiten:
            sh, sm, eh, em = self.tageszeiten[wochentag]
            start = sh * 60 + sm
            ende = eh * 60 + em
            return (start, ende)
        if wochentag in self.wochentage:
            return (
                self.start_stunde * 60 + self.start_minute,
                self.ende_stunde * 60 + self.ende_minute,
            )
        return None

    def arbeitszeit_fuer_tag(self, tag: dt.date) -> tuple[int, int] | None:
        """Start/Ende in Minuten seit Mitternacht für ein konkretes Datum."""
        return self.arbeitszeit_fuer_wochentag(tag.weekday())

    @property
    def start_minuten_seit_mitternacht(self) -> int:
        """Rückwärtskompatibel: generischer Startwert (Fallback, nicht taggenau)."""
        return self.start_stunde * 60 + self.start_minute

    @property
    def ende_minuten_seit_mitternacht(self) -> int:
        """Rückwärtskompatibel: generischer Endwert (Fallback, nicht taggenau)."""
        return self.ende_stunde * 60 + self.ende_minute

    def arbeitsflaechen_farbe_hex(self) -> str:
        return self.farbe_arbeit_hex or kalender_farben().REGELARBEIT_FLACHE


def standard_regelarbeit() -> RegelarbeitsProfil:
    """Voreinstellung: Mo–Fr, 10:00–19:00; Wochenende ohne Arbeit und Wegezeit."""
    return RegelarbeitsProfil(
        wochentage=werkwoch_wochentage(),
        start_stunde=10,
        start_minute=0,
        ende_stunde=19,
        ende_minute=0,
    )
