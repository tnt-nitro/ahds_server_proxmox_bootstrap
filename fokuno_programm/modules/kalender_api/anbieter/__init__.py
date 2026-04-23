"""Konkrete Kalender-Anbieter; neue Integrationen als eigene Datei + Klasse hier exportieren."""

from __future__ import annotations

from .alexa import AlexaKalenderAnbieter
from .apple import AppleKalenderAnbieter
from .google import GoogleKalenderAnbieter
from .outlook import OutlookKalenderAnbieter
from .thunderbird import ThunderbirdKalenderAnbieter

__all__ = [
    "AlexaKalenderAnbieter",
    "AppleKalenderAnbieter",
    "GoogleKalenderAnbieter",
    "OutlookKalenderAnbieter",
    "ThunderbirdKalenderAnbieter",
]
