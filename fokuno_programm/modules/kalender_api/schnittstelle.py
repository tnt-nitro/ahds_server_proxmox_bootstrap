"""Abstrakte Schnittstelle: Kalenderdaten einlesen und später zurück an Anbieter geben.

Zeitraum-Konvention für ``ereignisse_holen(von, bis)`` (AhDs, alle Implementierungen gleich):

- ``von`` und ``bis`` sind Kalendertage (**beide Grenzen inklusiv** als „welcher Tag gehört dazu“).
- Das Abfragefenster in **lokaler Zeit** (bzw. dokumentiert gleiche Basis-TZ):

  - **Start:** ``datetime.combine(von, datetime.time.min)``
  - **Ende (exklusiv):** erster Moment **nach** dem letzten Moment von ``bis``, also
    ``datetime.combine(bis + timedelta(days=1), datetime.time.min)``

- Ein ``KalenderEreignis`` gehört zur Antwort, wenn sein Zeitintervall das halboffene Fenster
  ``[fenster_start, fenster_ende_exklusiv)`` **überlappt**, d. h. üblich:

  ``ereignis.start < fenster_ende_exklusiv`` und ``ereignis.ende > fenster_start``

  (bei ganztägigen Terminen: ``ende`` wie vom Anbieter/AhDs-Modell definiert – konsistent halten).

Abweichungen nur mit ausdrücklichem Kommentar in der jeweiligen Anbieter-Implementierung.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Sequence

from .typen import KalenderEreignis


class KalenderAnbieter(ABC):
    """Ein externer Kalender (Google, Outlook, …).

    Implementierungen nur unter ``anbieter/``. Zeitraumlogik beim Lesen: siehe Modul-Docstring.
    """

    @property
    @abstractmethod
    def kennung(self) -> str:
        """Kurz-ID, stabil und maschinenlesbar, z. B. ``google`` (Logs, Konfiguration, UI-Schlüssel)."""

    @abstractmethod
    def ereignisse_holen(self, von: dt.date, bis: dt.date) -> Sequence[KalenderEreignis]:
        """Alle Ereignisse, die das AhDs-Abfragefenster aus *von*…*bis* überlappen.

        Args:
            von: Erster Kalendertag der Abfrage (inklusiv).
            bis: Letzter Kalendertag der Abfrage (inklusiv).

        Returns:
            Folge von ``KalenderEreignis``; Reihenfolge nicht garantiert, außer die
            Implementierung dokumentiert etwas anderes.

        Raises:
            NotImplementedError: bei Platzhaltern; bei echten APIs passende Fehler der Bibliothek
            oder eine klare AhDs-Exception-Schicht (später definieren).
        """

    def ereignisse_schreiben(self, ereignisse: Sequence[KalenderEreignis]) -> None:
        """Optional: Ereignisse an den Anbieter übertragen (anlegen/aktualisieren).

        Standard: nicht unterstützt → ``NotImplementedError``.
        """
        raise NotImplementedError(
            f"{self.kennung}: Schreiben ist für diesen Anbieter noch nicht umgesetzt."
        )


class KalenderAnbieterPlatzhalter(KalenderAnbieter):
    """Basis für Stubs bis zur echten API-Anbindung; ``ereignisse_holen`` wirft bewusst."""

    def __init__(self, kennung: str, anzeige_name: str) -> None:
        self._kennung = kennung
        self._anzeige = anzeige_name

    @property
    def kennung(self) -> str:
        return self._kennung

    def ereignisse_holen(self, von: dt.date, bis: dt.date) -> Sequence[KalenderEreignis]:
        raise NotImplementedError(
            f"{self._anzeige} ({self._kennung}): Anbindung folgt – siehe Regel ahds-kalender-api."
        )
