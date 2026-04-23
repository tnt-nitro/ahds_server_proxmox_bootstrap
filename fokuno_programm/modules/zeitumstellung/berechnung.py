"""Erkennt DST-Wechsel an einem Kalendertag für eine IANA-Zeitzone (Stdlib zoneinfo)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache
from zoneinfo import ZoneInfo


class ZeitumstellungArt(Enum):
    """Wechsel der UTC-Offset-Länge (lokale Uhr springt vor oder zurück)."""

    SOMMERZEIT_BEGINN = auto()
    NORMALZEIT_BEGINN = auto()


@dataclass(frozen=True)
class ZeitumstellungAmTag:
    """Erster Zeitpunkt nach dem Offset-Wechsel (typisch 03:00 Wanduhr in DE)."""

    art: ZeitumstellungArt
    zeitpunkt: dt.datetime
    zeitzone: str


@lru_cache(maxsize=512)
def umstellung_am_tag(datum: dt.date, zeitzone: str) -> ZeitumstellungAmTag | None:
    """Liefert den Umstellungszeitpunkt, falls ``datum`` in ``zeitzone`` genau einen DST-Wechsel hat.

    Die Erkennung vergleicht ``utcoffset()`` in Echtzeit-Schritten ab lokaler Mitternacht
    (funktioniert für EU/Berlin und andere zoneinfo-Regeln; kein Länder-Hardcode).
    """
    tz = ZoneInfo(zeitzone)
    mitternacht = dt.datetime.combine(datum, dt.time(0, 0), tzinfo=tz)
    vorher = mitternacht.utcoffset()
    for mi in range(1, 24 * 60 + 2):
        t = mitternacht + dt.timedelta(minutes=mi)
        neu = t.utcoffset()
        if neu != vorher:
            art = (
                ZeitumstellungArt.SOMMERZEIT_BEGINN
                if neu > vorher
                else ZeitumstellungArt.NORMALZEIT_BEGINN
            )
            return ZeitumstellungAmTag(art=art, zeitpunkt=t, zeitzone=zeitzone)
        vorher = neu
    return None
