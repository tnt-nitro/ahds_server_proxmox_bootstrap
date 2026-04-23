"""Apple (Kalender, iCloud) – später z. B. EventKit (macOS/iOS), CalDAV zu iCloud, Apple-APIs."""

from __future__ import annotations

from ..schnittstelle import KalenderAnbieterPlatzhalter


class AppleKalenderAnbieter(KalenderAnbieterPlatzhalter):
    def __init__(self) -> None:
        super().__init__("apple", "Apple Kalender / iCloud")
