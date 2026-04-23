"""Lokale Zeitblöcke (Aufzeichnung) für die Kalender-Tagesansicht.

Persistenz: ``~/AhDs/Kalender/zeitbloecke.json``
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

_listeners: list[Callable[[], None]] = []


def _datei_pfad() -> Path:
    p = Path.home() / "AhDs" / "Kalender"
    p.mkdir(parents=True, exist_ok=True)
    return p / "zeitbloecke.json"


def listener_registrieren(fn: Callable[[], None]) -> None:
    """Kalender-Ansichten melden sich an, um nach „Einfügen“ neu zu zeichnen."""
    if fn not in _listeners:
        _listeners.append(fn)


def listener_entfernen(fn: Callable[[], None]) -> None:
    try:
        _listeners.remove(fn)
    except ValueError:
        pass


def _benachrichtigen() -> None:
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            pass


@dataclass(frozen=True)
class ZeitblockEintrag:
    id: str
    start: dt.datetime
    ende: dt.datetime
    titel: str
    #: Wenn gesetzt: Klick im Kalender oeffnet diesen Kontakt (Kontakte-Modul).
    kontakt_id: str = ""


def _zeilen_laden() -> list[dict[str, object]]:
    pf = _datei_pfad()
    if not pf.is_file():
        return []
    try:
        roh = json.loads(pf.read_text(encoding="utf-8"))
        return list(roh.get("eintraege", []))
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _zeilen_speichern(zeilen: list[dict[str, object]]) -> None:
    _datei_pfad().write_text(
        json.dumps({"eintraege": zeilen}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def alle_eintraege() -> list[ZeitblockEintrag]:
    """Alle gespeicherten Blöcke (neueste Logik: Reihenfolge wie in der Datei)."""
    out: list[ZeitblockEintrag] = []
    for z in _zeilen_laden():
        try:
            sid = str(z["id"])
            start = dt.datetime.fromisoformat(str(z["start"]))
            ende = dt.datetime.fromisoformat(str(z["ende"]))
            titel = str(z.get("titel", ""))
            kid = str(z.get("kontakt_id", "")).strip()
            out.append(ZeitblockEintrag(sid, start, ende, titel, kid))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def einfuegen(start: dt.datetime, ende: dt.datetime, titel: str) -> None:
    """Neuen Block speichern und registrierte Kalenderansichten auffrischen."""
    if start >= ende:
        return
    zeilen = _zeilen_laden()
    zeilen.append(
        {
            "id": str(uuid.uuid4()),
            "start": start.isoformat(),
            "ende": ende.isoformat(),
            "titel": titel.strip(),
            "kontakt_id": "",
        }
    )
    _zeilen_speichern(zeilen)
    _benachrichtigen()


def kontakt_bearbeitung_spur_setzen(
    kontakt_id: str,
    titel: str,
    zeitpunkt: dt.datetime,
    tz: ZoneInfo,
    dauer_minuten: int = 15,
) -> None:
    """Ersetzt die Kalender-Spur fuer einen Kontakt (letzte Bearbeitung sichtbar im Blatt)."""
    kid = kontakt_id.strip()
    if not kid:
        return
    zeilen = _zeilen_laden()
    zeilen = [z for z in zeilen if str(z.get("kontakt_id", "")).strip() != kid]
    zt = zeitpunkt
    if zt.tzinfo is None:
        zt = zt.replace(tzinfo=tz)
    else:
        zt = zt.astimezone(tz)
    ende = zt + dt.timedelta(minutes=max(1, dauer_minuten))
    zeilen.append(
        {
            "id": str(uuid.uuid4()),
            "start": zt.isoformat(),
            "ende": ende.isoformat(),
            "titel": titel.strip(),
            "kontakt_id": kid,
        }
    )
    _zeilen_speichern(zeilen)
    _benachrichtigen()


def eintrag_existiert(start: dt.datetime, ende: dt.datetime, titel: str) -> bool:
    """Prueft auf identischen Start/Ende/Titel-Datensatz."""
    such_titel = titel.strip()
    for e in alle_eintraege():
        if e.start == start and e.ende == ende and e.titel == such_titel:
            return True
    return False


def einfuegen_wenn_fehlt(start: dt.datetime, ende: dt.datetime, titel: str) -> bool:
    """Fuegt nur ein, wenn derselbe Datensatz noch nicht vorhanden ist."""
    if start >= ende:
        return False
    if eintrag_existiert(start, ende, titel):
        return False
    einfuegen(start, ende, titel)
    return True


def _dt_in_tz(t: dt.datetime, tz: ZoneInfo) -> dt.datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=tz)
    return t.astimezone(tz)


def segmente_minuten_fuer_tag(tag: dt.date, tz: ZoneInfo) -> list[tuple[float, float]]:
    """Sichtbare Minutenintervalle (0–1440+) relativ zu Mitternacht von ``tag`` in ``tz``."""
    return [(m0, m1) for m0, m1, _titel, _kid in segmente_minuten_mit_titel_fuer_tag(tag, tz)]


def segmente_minuten_mit_titel_fuer_tag(
    tag: dt.date, tz: ZoneInfo
) -> list[tuple[float, float, str, str]]:
    """Wie :func:`segmente_minuten_fuer_tag`, inkl. Titel und optionaler Kontakt-ID."""
    tag_start = dt.datetime.combine(tag, dt.time.min, tzinfo=tz)
    tag_ende = tag_start + dt.timedelta(days=1)
    seg: list[tuple[float, float, str, str]] = []
    for e in alle_eintraege():
        a = _dt_in_tz(e.start, tz)
        b = _dt_in_tz(e.ende, tz)
        lo = max(a, tag_start)
        hi = min(b, tag_ende)
        if lo < hi:
            m0 = (lo - tag_start).total_seconds() / 60.0
            m1 = (hi - tag_start).total_seconds() / 60.0
            seg.append((m0, m1, e.titel, e.kontakt_id))
    return seg


def segmente_datetime_mitlauf(
    t_top: dt.datetime, t_bot: dt.datetime, tz: ZoneInfo
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Überlappung mit dem Mitlauf-Fenster ``[t_top, t_bot)``."""
    return [
        (start, ende)
        for start, ende, _titel, _kid in segmente_datetime_mitlauf_mit_titel(t_top, t_bot, tz)
    ]


def segmente_datetime_mitlauf_mit_titel(
    t_top: dt.datetime, t_bot: dt.datetime, tz: ZoneInfo
) -> list[tuple[dt.datetime, dt.datetime, str, str]]:
    """Wie :func:`segmente_datetime_mitlauf`, inkl. Titel und optionaler Kontakt-ID."""
    out: list[tuple[dt.datetime, dt.datetime, str, str]] = []
    for e in alle_eintraege():
        a = _dt_in_tz(e.start, tz)
        b = _dt_in_tz(e.ende, tz)
        lo = max(a, t_top)
        hi = min(b, t_bot)
        if lo < hi:
            out.append((lo, hi, e.titel, e.kontakt_id))
    return out
