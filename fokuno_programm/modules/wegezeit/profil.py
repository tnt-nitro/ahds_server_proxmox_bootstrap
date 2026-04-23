"""Wegezeit Wohnung ↔ Arbeit. Ausbau später: Modi (Auto, Fahrrad, ÖPNV, Fuß, …) mit je eigener Dauer."""

from __future__ import annotations

from dataclasses import dataclass

from modules.theming.farben import kalender_farben


@dataclass(frozen=True)
class WegezeitProfil:
    """Hin- und Rückweg in Minuten (pro Arbeitstag an die Regelarbeitszeiten gekoppelt)."""

    minuten_hin_zur_arbeit: int
    minuten_rueck_nach_hause: int
    farbe_weg_hex: str | None = None

    def wegflaechen_farbe_hex(self) -> str:
        return self.farbe_weg_hex or kalender_farben().WEGEZEIT_FLACHE


def standard_wegezeit() -> WegezeitProfil:
    """Voreinstellung: je 30 Minuten Hin- und Rückweg."""
    return WegezeitProfil(
        minuten_hin_zur_arbeit=30,
        minuten_rueck_nach_hause=30,
    )
