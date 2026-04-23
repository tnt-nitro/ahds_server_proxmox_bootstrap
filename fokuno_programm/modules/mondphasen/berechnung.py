"""Synodische Mondphase aus dem Kalenderdatum (ohne Zusatzbibliotheken)."""

from __future__ import annotations

import datetime as dt
import math
from typing import Final

# Länge der synodischen Periode [Tage]
_SYNODE: Final[float] = 29.530588853
# Bezugs-Neumond (näherungsweise), Julianische Datum-Mitte des Tages
_REF_NEUMOND_JD: Final[float] = 2451550.09766


def _julianisches_datum_mitternacht_utc(d: dt.date) -> float:
    """JD um 00:00 UTC des gregorianischen Datums (für Phasen-Näherung)."""
    y, m, day = d.year, d.month, d.day
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + (a // 4)
    jd = int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5
    return float(jd)


def mondphase_synode_anteil(datum: dt.date) -> float:
    """Anteil der Synode in :math:`[0, 1)`.

    * ``0`` ≈ Neumond, ``0.25`` erstes Viertel, ``0.5`` ≈ Vollmond,
      ``0.75`` letztes Viertel, gegen ``1`` wieder Neumond.
    """
    jd = _julianisches_datum_mitternacht_utc(datum)
    alter = (jd - _REF_NEUMOND_JD) % _SYNODE
    return alter / _SYNODE


def mondphase_beleuchtungsanteil(phase_0_1: float) -> float:
    """Sichtbar beleuchteter Anteil der Mondscheibe, :math:`[0,1]`."""
    return 0.5 * (1.0 - math.cos(2.0 * math.pi * phase_0_1))
