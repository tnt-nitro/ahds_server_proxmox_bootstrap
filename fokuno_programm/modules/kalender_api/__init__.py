"""Schnittstelle für Kalenderdaten nach außen und von außen – Anbieter unter `anbieter/`."""

from __future__ import annotations

from . import anbieter
from .schnittstelle import KalenderAnbieter, KalenderAnbieterPlatzhalter
from .typen import KalenderEreignis

__all__ = [
    "anbieter",
    "KalenderAnbieter",
    "KalenderAnbieterPlatzhalter",
    "KalenderEreignis",
]
