"""Gemeinsame Kalender-Daten für alle externen Anbieter (AhDs-internes Modell).

Mapping von Anbieter-Rohdaten (Google, ICS, …) erfolgt in den jeweiligen ``anbieter``-Modulen;
dieses Modul bleibt bewusst schlank.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class KalenderEreignis:
    """Ein Termin oder Zeitblock im AhDs-Kalendermodell.

    Attributes:
        titel: Kurzer Anzeigename (leerer String erlaubt, wenn der Anbieter nichts liefert).
        start: Beginn; **naiv oder aware** – alle Anbieter einer Installation sollten dieselbe
            Konvention nutzen (typisch: lokale naive Zeit oder durchgängig UTC mit TZ-Info).
        ende: Ende des Blocks; es wird **start < ende** erwartet (außer dokumentierte Sonderfälle
            für ganztägige Events, dann konsistent mit der gewählten Ganztags-Semantik).
        ganztaegig: True, wenn es sich um einen ganztägigen Eintrag handelt; ``start``/``ende``
            müssen dann zur gewählten Ganztags-Konvention passen (z. B. 00:00–00:00 Folgetag).
        externe_id: ID beim Anbieter, falls vorhanden (Sync, Updates, Löschen).
        quelle_kennung: Optional gleich ``KalenderAnbieter.kennung`` nach dem Import (Provenienz).
    """

    titel: str
    start: dt.datetime
    ende: dt.datetime
    ganztaegig: bool = False
    externe_id: str | None = None
    quelle_kennung: str | None = None
