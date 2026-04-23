"""Microsoft Outlook / Microsoft 365 – später z. B. Microsoft Graph (Kalender)."""

from __future__ import annotations

from ..schnittstelle import KalenderAnbieterPlatzhalter


class OutlookKalenderAnbieter(KalenderAnbieterPlatzhalter):
    def __init__(self) -> None:
        super().__init__("outlook", "Outlook / Microsoft 365")
