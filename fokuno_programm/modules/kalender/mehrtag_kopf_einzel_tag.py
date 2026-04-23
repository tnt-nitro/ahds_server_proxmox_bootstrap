"""Mehrtag-Kopfzeile: Klick springt in die Ein-Tages-Ansicht für den gewählten Kalendertag."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable


def sprung_zu_einzel_tag(
    tag: dt.date,
    *,
    zeitraum_auf_tag_stellen: Callable[[], None],
    kalendertag_anzeigen: Callable[[dt.date], None],
) -> None:
    """Zuerst Zeitraum „Tag“ wählen, dann das Datum setzen (Nav-Leiste und Raster bleiben konsistent)."""
    zeitraum_auf_tag_stellen()
    kalendertag_anzeigen(tag)
