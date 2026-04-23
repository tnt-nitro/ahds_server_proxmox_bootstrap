"""Mozilla Thunderbird – später z. B. lokale CalDAV-Konten, ICS-Import/Export, Lightning."""

from __future__ import annotations

from ..schnittstelle import KalenderAnbieterPlatzhalter


class ThunderbirdKalenderAnbieter(KalenderAnbieterPlatzhalter):
    def __init__(self) -> None:
        super().__init__("thunderbird", "Mozilla Thunderbird")
