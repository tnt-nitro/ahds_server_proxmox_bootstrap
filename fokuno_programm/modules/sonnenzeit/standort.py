"""Beobachtungsort für Sonnenauf- und -untergang (später z. B. GPS aus der App)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StandortProfil:
    """Breiten-/Längengrad in Dezimalgrad, IANA-Zeitzonenname."""

    ortsname: str
    breitengrad: float
    laengengrad: float
    zeitzone: str


def standard_frankfurt_am_main() -> StandortProfil:
    """Default: Frankfurt am Main, Europe/Berlin."""
    return StandortProfil(
        ortsname="Frankfurt am Main, DE",
        breitengrad=50.110924,
        laengengrad=8.682127,
        zeitzone="Europe/Berlin",
    )
