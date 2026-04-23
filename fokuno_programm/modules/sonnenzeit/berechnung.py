"""Sonnenstand / zivile Dämmerung standortbezogen (astral)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from zoneinfo import ZoneInfo

from .standort import StandortProfil

_NACHT: Final[float] = 0.0
_TAG: Final[float] = 1.0


@dataclass(frozen=True)
class SonnenTagZeiten:
    """Zivile Dämmerung (6°) und Sonnenauf-/untergang; Zeiten timezone-aware."""

    morgendaemmerung: dt.datetime
    sonnenaufgang: dt.datetime
    sonnenuntergang: dt.datetime
    abenddaemmerung: dt.datetime


@dataclass(frozen=True)
class NautischeDaemmerung:
    """Nautische Dämmerung (12° unter dem Horizont), timezone-aware.

    *morgens*: Beginn der nautischen Morgendämmerung (Sonne steigt auf −12°).
    *abends*: Ende der nautischen Abenddämmerung (Sonne sinkt auf −12°).
    """

    morgens: dt.datetime
    abends: dt.datetime


@dataclass(frozen=True)
class SonnenKulmination:
    """Oberkulmination (Sonnenhöchststand) und Unterkulmination (Sonnenmitternacht).

    Entspricht astral ``noon`` bzw. ``midnight``: Sonne im Meridian (höchster
    Stand) bzw. gegenüber der Beobachterposition (tiefster Stand; nicht die
    Uhrzeit-Mitternacht 00:00).
    """

    oberkulmination: dt.datetime
    unterkulmination: dt.datetime


def _linear(t: float, a: float, b: float, ya: float, yb: float) -> float:
    if b <= a:
        return ya
    return ya + (t - a) / (b - a) * (yb - ya)


@lru_cache(maxsize=256)
def _sonnenzeiten_cached(
    ort: str,
    breite: float,
    laenge: float,
    tz_name: str,
    jahr: int,
    monat: int,
    tag: int,
) -> tuple[dt.datetime, dt.datetime, dt.datetime, dt.datetime] | None:
    from astral import LocationInfo
    from astral.sun import sun

    datum = dt.date(jahr, monat, tag)
    tz = ZoneInfo(tz_name)
    kurz = ort[:32] if ort else "Ort"
    loc = LocationInfo(kurz, "", tz_name, breite, laenge)
    s = sun(loc.observer, date=datum, tzinfo=tz)
    dawn, sr, ss, dusk = s["dawn"], s["sunrise"], s["sunset"], s["dusk"]
    if dawn is None or sr is None or ss is None or dusk is None:
        return None
    return (dawn, sr, ss, dusk)


def sonnenzeiten_am_tag(datum: dt.date, standort: StandortProfil) -> SonnenTagZeiten | None:
    """Liefert zivile Dämmerung und Sonne oder ``None`` (Polarnacht/-tag o. Ä.)."""
    tup = _sonnenzeiten_cached(
        standort.ortsname,
        standort.breitengrad,
        standort.laengengrad,
        standort.zeitzone,
        datum.year,
        datum.month,
        datum.day,
    )
    if tup is None:
        return None
    d, sr, ss, du = tup
    return SonnenTagZeiten(
        morgendaemmerung=d,
        sonnenaufgang=sr,
        sonnenuntergang=ss,
        abenddaemmerung=du,
    )


@lru_cache(maxsize=256)
def _nautische_daemmerung_cached(
    ort: str,
    breite: float,
    laenge: float,
    tz_name: str,
    jahr: int,
    monat: int,
    tag: int,
) -> tuple[dt.datetime, dt.datetime] | None:
    from astral import Depression, LocationInfo
    from astral.sun import sun

    datum = dt.date(jahr, monat, tag)
    tz = ZoneInfo(tz_name)
    kurz = ort[:32] if ort else "Ort"
    loc = LocationInfo(kurz, "", tz_name, breite, laenge)
    s = sun(
        loc.observer,
        date=datum,
        dawn_dusk_depression=Depression.NAUTICAL,
        tzinfo=tz,
    )
    dawn, dusk = s["dawn"], s["dusk"]
    if dawn is None or dusk is None:
        return None
    return (dawn, dusk)


def nautische_daemmerung_am_tag(
    datum: dt.date, standort: StandortProfil
) -> NautischeDaemmerung | None:
    """Nautische Dämmerung (12°) oder ``None`` bei Polarnacht/-tag o. Ä."""
    tup = _nautische_daemmerung_cached(
        standort.ortsname,
        standort.breitengrad,
        standort.laengengrad,
        standort.zeitzone,
        datum.year,
        datum.month,
        datum.day,
    )
    if tup is None:
        return None
    morgens, abends = tup
    return NautischeDaemmerung(morgens=morgens, abends=abends)


@lru_cache(maxsize=256)
def _sonnen_kulmination_cached(
    ort: str,
    breite: float,
    laenge: float,
    tz_name: str,
    jahr: int,
    monat: int,
    tag: int,
) -> tuple[dt.datetime, dt.datetime] | None:
    from astral import LocationInfo
    from astral.sun import midnight, noon

    datum = dt.date(jahr, monat, tag)
    tz = ZoneInfo(tz_name)
    kurz = ort[:32] if ort else "Ort"
    loc = LocationInfo(kurz, "", tz_name, breite, laenge)
    try:
        o = noon(loc.observer, date=datum, tzinfo=tz)
        u = midnight(loc.observer, date=datum, tzinfo=tz)
    except (TypeError, ValueError):
        return None
    return (o, u)


def sonnen_kulmination_am_tag(
    datum: dt.date, standort: StandortProfil
) -> SonnenKulmination | None:
    """Ober- und Unterkulmination oder ``None`` bei fehlender Berechnung."""
    tup = _sonnen_kulmination_cached(
        standort.ortsname,
        standort.breitengrad,
        standort.laengengrad,
        standort.zeitzone,
        datum.year,
        datum.month,
        datum.day,
    )
    if tup is None:
        return None
    ober, unter = tup
    return SonnenKulmination(oberkulmination=ober, unterkulmination=unter)


def helligkeit_01(t: dt.datetime, z: SonnenTagZeiten) -> float:
    """0 = Nacht (schwarz), 1 = heller Tag (gelb), dazwischen lineare Dämmerung."""
    if t.tzinfo is None:
        raise ValueError("helligkeit_01: t muss timezone-aware sein.")
    if t < z.morgendaemmerung:
        return _NACHT
    if t < z.sonnenaufgang:
        return _linear(
            t.timestamp(),
            z.morgendaemmerung.timestamp(),
            z.sonnenaufgang.timestamp(),
            _NACHT,
            _TAG,
        )
    if t <= z.sonnenuntergang:
        return _TAG
    if t <= z.abenddaemmerung:
        return _linear(
            t.timestamp(),
            z.sonnenuntergang.timestamp(),
            z.abenddaemmerung.timestamp(),
            _TAG,
            _NACHT,
        )
    return _NACHT


def farbe_sonnenstreifen(helligkeit: float) -> str:
    """Interpolation Schwarz → Gelb (#FFEB3B) für ``helligkeit`` in [0, 1]."""
    h = max(0.0, min(1.0, helligkeit))
    r = int(0 + h * 255)
    g = int(0 + h * 235)
    b = int(0 + h * 59)
    return f"#{r:02x}{g:02x}{b:02x}"


def datetime_aus_datum_und_minute_float(
    datum: dt.date,
    minute_seit_mitternacht: float,
    zeitzone: str,
) -> dt.datetime:
    """Lokaler Zeitpunkt an ``datum`` aus Minuten seit Mitternacht (float)."""
    tz = ZoneInfo(zeitzone)
    basis = dt.datetime.combine(datum, dt.time.min, tzinfo=tz)
    return basis + dt.timedelta(minutes=minute_seit_mitternacht)
