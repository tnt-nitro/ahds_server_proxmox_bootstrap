"""Kalenderfarben: Hell- und Dunkelpalette, abhängig vom globalen Erscheinungsmodus.

Statische Referenz für die Cursor-Regel ahds-farben: Werte der **Normalpalette** dort pflegen;
Dunkelwerte hier in ``_KALENDER_DUNKEL`` spiegeln.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modus import ist_darkmode


@dataclass(frozen=True)
class KalenderFarbenPaket:
    HINTERGRUND_BLATT: str
    HINTERGRUND_ZEITLEISTE: str
    HINTERGRUND_FENSTER: str
    PHASE_WACH: str
    PHASE_SCHLAF: str
    REGELARBEIT_FLACHE: str
    WEGEZEIT_FLACHE: str
    PAUSE_ARBEIT_FLACHE: str
    #: Nutzer-Zeitaufzeichnung (Gewohnheiten / wo Zeit hingeht).
    ZEITAUFZEICHNUNG_FLACHE: str
    TRENNLINIE: str
    RASTER_STUNDE: str
    TEXT_ZEIT: str
    #: Unterkulmination (über Mond): Füllung; ruhiges Blaugrau, nicht signalrot.
    TEXT_UNTERKULMINATION: str
    #: Dünner Umriss für Lesbarkeit auf Neumond (schwarz) und Vollmond (hell).
    TEXT_UNTERKULMINATION_RAND: str
    #: Sonnenhöchstand-Icon hinter der Oberkulminationszeit (Zeitleiste).
    ICON_SONNE_FLAECE: str
    ICON_SONNE_STRAHL: str
    JETZT_ZEIGER: str
    JETZT_ZEIGER_RAND: str
    JETZT_BANNER_TEXT: str
    #: Horizontale Markierung DST-Umstellung (unterscheidet sich vom Jetzt-Zeiger).
    ZEITUMSTELLUNG_LINIE: str


_KALENDER_HELL = KalenderFarbenPaket(
    HINTERGRUND_BLATT="#F7F4EF",
    HINTERGRUND_ZEITLEISTE="#E8E4DC",
    HINTERGRUND_FENSTER="#EDE9E2",
    PHASE_WACH="#FFF0C2",
    PHASE_SCHLAF="#D4E5F7",
    REGELARBEIT_FLACHE="#C4E0A8",
    WEGEZEIT_FLACHE="#E2C77A",
    PAUSE_ARBEIT_FLACHE="#C9B8D9",
    ZEITAUFZEICHNUNG_FLACHE="#9BC4BC",
    TRENNLINIE="#C4BDB0",
    RASTER_STUNDE="#D9D4CA",
    TEXT_ZEIT="#3D3A36",
    TEXT_UNTERKULMINATION="#2D4A52",
    TEXT_UNTERKULMINATION_RAND="#F2EDE2",
    ICON_SONNE_FLAECE="#FFE082",
    ICON_SONNE_STRAHL="#D9A300",
    JETZT_ZEIGER="#C45C3E",
    JETZT_ZEIGER_RAND="#8F3D2A",
    JETZT_BANNER_TEXT="#FFFFFF",
    ZEITUMSTELLUNG_LINIE="#C17817",
)

_KALENDER_DUNKEL = KalenderFarbenPaket(
    HINTERGRUND_BLATT="#252320",
    HINTERGRUND_ZEITLEISTE="#2F2C28",
    HINTERGRUND_FENSTER="#201E1C",
    PHASE_WACH="#5C4E2E",
    PHASE_SCHLAF="#2A3A52",
    REGELARBEIT_FLACHE="#3D5A3F",
    WEGEZEIT_FLACHE="#6B5A2A",
    PAUSE_ARBEIT_FLACHE="#4A3D58",
    ZEITAUFZEICHNUNG_FLACHE="#3D6B63",
    TRENNLINIE="#5A5650",
    RASTER_STUNDE="#45423C",
    TEXT_ZEIT="#E8E4DC",
    TEXT_UNTERKULMINATION="#B9CDE0",
    TEXT_UNTERKULMINATION_RAND="#101010",
    ICON_SONNE_FLAECE="#FFCA28",
    ICON_SONNE_STRAHL="#F57F17",
    JETZT_ZEIGER="#E07A5A",
    JETZT_ZEIGER_RAND="#A84830",
    JETZT_BANNER_TEXT="#FFFFFF",
    ZEITUMSTELLUNG_LINIE="#E8A42C",
)


def kalender_farben() -> KalenderFarbenPaket:
    """Aktives Farbset für die Kalenderzeichnung (abhängig von ``modus.ist_darkmode()``)."""
    return _KALENDER_DUNKEL if ist_darkmode() else _KALENDER_HELL
