"""Google Calendar – später z. B. Google Calendar API, OAuth 2.0, `google-api-python-client`."""

from __future__ import annotations

from ..schnittstelle import KalenderAnbieterPlatzhalter


class GoogleKalenderAnbieter(KalenderAnbieterPlatzhalter):
    def __init__(self) -> None:
        super().__init__("google", "Google Calendar")
