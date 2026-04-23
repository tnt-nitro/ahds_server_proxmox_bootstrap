"""Amazon Alexa – später z. B. Alexa Skills Kit / verknüpfte Kalender (nicht identisch mit CalDAV)."""

from __future__ import annotations

from ..schnittstelle import KalenderAnbieterPlatzhalter


class AlexaKalenderAnbieter(KalenderAnbieterPlatzhalter):
    def __init__(self) -> None:
        super().__init__("alexa", "Amazon Alexa")
