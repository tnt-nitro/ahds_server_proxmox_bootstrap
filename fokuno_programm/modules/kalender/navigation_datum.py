"""Hilfsfunktionen für Kalendernavigation (Sprungziele als Datum)."""

from __future__ import annotations

import datetime as dt
from enum import Enum, auto


class KalenderNavigationIntervall(Enum):
    """Zeitraum-Auswahl in der Navigationsleiste (Anzeige weiterhin Tagesansicht)."""

    TAG = auto()
    DREI_TAGE = auto()
    WOCHE = auto()
    ARBEITSWOCHE = auto()
    WOCHENENDE = auto()
    MONAT = auto()
    JAHR = auto()


def datum_gestern() -> dt.date:
    return dt.date.today() - dt.timedelta(days=1)


def datum_heute() -> dt.date:
    return dt.date.today()


def datum_morgen() -> dt.date:
    return dt.date.today() + dt.timedelta(days=1)


def datum_letzte_3_tage_erster() -> dt.date:
    """Erster Tag des vorherigen 3-Tage-Blocks (Schrittweite 3, bezogen auf heute)."""
    return dt.date.today() - dt.timedelta(days=3)


def datum_diese_3_tage_erster() -> dt.date:
    """Erster Tag des aktuellen 3-Tage-Blocks (= heute)."""
    return dt.date.today()


def datum_naechste_3_tage_erster() -> dt.date:
    """Erster Tag des nächsten 3-Tage-Blocks."""
    return dt.date.today() + dt.timedelta(days=3)


def datum_samstag_in_iso_woche_von(d: dt.date) -> dt.date:
    """Samstag der Kalenderwoche (Mo–So), die ``d`` enthält."""
    montag = d - dt.timedelta(days=d.weekday())
    return montag + dt.timedelta(days=5)


def montag_diese_woche() -> dt.date:
    t = dt.date.today()
    return t - dt.timedelta(days=t.weekday())


def datum_letzte_woche_montag() -> dt.date:
    return montag_diese_woche() - dt.timedelta(days=7)


def datum_diese_woche_montag() -> dt.date:
    return montag_diese_woche()


def datum_naechste_woche_montag() -> dt.date:
    return montag_diese_woche() + dt.timedelta(days=7)


def datum_letztes_wochenende_samstag() -> dt.date:
    """Samstag der direkt vorangehenden ISO-Kalenderwoche (Mo–So)."""
    m = montag_diese_woche()
    return m - dt.timedelta(days=2)


def datum_dieses_wochenende_samstag() -> dt.date:
    """Samstag der aktuellen ISO-Kalenderwoche."""
    return datum_samstag_in_iso_woche_von(dt.date.today())


def datum_naechstes_wochenende_samstag() -> dt.date:
    """Samstag der folgenden ISO-Kalenderwoche."""
    m = montag_diese_woche()
    return m + dt.timedelta(days=12)


def datum_letzter_monat_erster() -> dt.date:
    t = dt.date.today()
    if t.month == 1:
        return dt.date(t.year - 1, 12, 1)
    return dt.date(t.year, t.month - 1, 1)


def datum_dieser_monat_erster() -> dt.date:
    t = dt.date.today()
    return dt.date(t.year, t.month, 1)


def datum_naechster_monat_erster() -> dt.date:
    t = dt.date.today()
    if t.month == 12:
        return dt.date(t.year + 1, 1, 1)
    return dt.date(t.year, t.month + 1, 1)


def datum_letztes_jahr_erster() -> dt.date:
    y = dt.date.today().year - 1
    return dt.date(y, 1, 1)


def datum_dieses_jahr_erster() -> dt.date:
    y = dt.date.today().year
    return dt.date(y, 1, 1)


def datum_naechstes_jahr_erster() -> dt.date:
    y = dt.date.today().year + 1
    return dt.date(y, 1, 1)


def datum_kalendermonat_schritt(basis: dt.date, richtung: int) -> dt.date:
    """Erster Tag des vorherigen bzw. nächsten Kalendermonats relativ zum Monat von ``basis``."""
    erster = dt.date(basis.year, basis.month, 1)
    if richtung < 0:
        if erster.month == 1:
            return dt.date(erster.year - 1, 12, 1)
        return dt.date(erster.year, erster.month - 1, 1)
    if erster.month == 12:
        return dt.date(erster.year + 1, 1, 1)
    return dt.date(erster.year, erster.month + 1, 1)


def datum_kalenderjahr_schritt(basis: dt.date, richtung: int) -> dt.date:
    """1. Januar des vorherigen bzw. nächsten Jahres relativ zum Jahr von ``basis``."""
    j = basis.year
    if richtung < 0:
        return dt.date(j - 1, 1, 1)
    return dt.date(j + 1, 1, 1)
