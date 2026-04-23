"""Speicherlogik fuer Schatzkisten-Eintraege."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.kalender.zeitaufzeichnung_speicher import einfuegen_wenn_fehlt

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_KALENDER_SYMBOL_STANDARD = "\u25A4"


def _datei_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Schatzkiste"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "eintraege.json"


def _plus_monate(zeitpunkt: dt.datetime, monate: int) -> dt.datetime:
    basis_monat = zeitpunkt.month - 1 + monate
    jahr = zeitpunkt.year + basis_monat // 12
    monat = basis_monat % 12 + 1
    tage_im_monat = (
        dt.date(jahr + (monat // 12), (monat % 12) + 1, 1) - dt.timedelta(days=1)
    ).day
    tag = min(zeitpunkt.day, tage_im_monat)
    return zeitpunkt.replace(year=jahr, month=monat, day=tag)


def _nico_startzeitpunkt() -> dt.datetime:
    return dt.datetime(2026, 4, 9, 17, 15, tzinfo=_TZ_BERLIN)


def _nico_text_was_ist_passiert() -> str:
    return (
        "Ich habe heute von der ADHS Gruppe auf einem Zettel Wuensche notiert bekommen. "
        "Wenn mich das noch interessiert werde ich sie lesen. "
        "Ich werde einen ruhigen schoenen Platz dafuer aussuchen und mich dabei filmen. "
        "Das Video stelle ich dann in die ADHS Gruppe."
    )


@dataclass(frozen=True)
class SchatzkistenEintrag:
    id: str
    konto_name: str
    erstellt_am: dt.datetime
    ort: str
    text_inhalt: str
    text_in_drei_monaten: str
    oeffnen_am: dt.datetime
    kalender_symbol: str
    kalender_titel_start: str
    kalender_titel_oeffnen: str
    nach_schliessen_gesperrt: bool


def _roh_laden() -> list[dict[str, object]]:
    pfad = _datei_pfad()
    if not pfad.is_file():
        return []
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    return list(roh.get("eintraege", []))


def _roh_speichern(eintraege: list[dict[str, object]]) -> None:
    _datei_pfad().write_text(
        json.dumps({"eintraege": eintraege}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _aus_roh(zeile: dict[str, object]) -> SchatzkistenEintrag | None:
    try:
        return SchatzkistenEintrag(
            id=str(zeile["id"]),
            konto_name=str(zeile["konto_name"]),
            erstellt_am=dt.datetime.fromisoformat(str(zeile["erstellt_am"])),
            ort=str(zeile["ort"]),
            text_inhalt=str(zeile["text_inhalt"]),
            text_in_drei_monaten=str(zeile["text_in_drei_monaten"]),
            oeffnen_am=dt.datetime.fromisoformat(str(zeile["oeffnen_am"])),
            kalender_symbol=str(
                zeile.get("kalender_symbol", _KALENDER_SYMBOL_STANDARD)
            ),
            kalender_titel_start=str(zeile["kalender_titel_start"]),
            kalender_titel_oeffnen=str(zeile["kalender_titel_oeffnen"]),
            nach_schliessen_gesperrt=bool(zeile.get("nach_schliessen_gesperrt", True)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _als_roh(eintrag: SchatzkistenEintrag) -> dict[str, object]:
    return {
        "id": eintrag.id,
        "konto_name": eintrag.konto_name,
        "erstellt_am": eintrag.erstellt_am.isoformat(),
        "ort": eintrag.ort,
        "text_inhalt": eintrag.text_inhalt,
        "text_in_drei_monaten": eintrag.text_in_drei_monaten,
        "oeffnen_am": eintrag.oeffnen_am.isoformat(),
        "kalender_symbol": eintrag.kalender_symbol,
        "kalender_titel_start": eintrag.kalender_titel_start,
        "kalender_titel_oeffnen": eintrag.kalender_titel_oeffnen,
        "nach_schliessen_gesperrt": eintrag.nach_schliessen_gesperrt,
    }


def alle_eintraege() -> list[SchatzkistenEintrag]:
    out: list[SchatzkistenEintrag] = []
    for zeile in _roh_laden():
        eintrag = _aus_roh(zeile)
        if eintrag is not None:
            out.append(eintrag)
    return out


def _nico_start_eintrag() -> SchatzkistenEintrag:
    start = _nico_startzeitpunkt()
    start_titel = f"{_KALENDER_SYMBOL_STANDARD} Schatzkiste befuellt (Nico)"
    oeffnen_titel = (
        f"{_KALENDER_SYMBOL_STANDARD} Schatzkiste oeffnen (Nico, Rueckblick nach 3 Monaten)"
    )
    return SchatzkistenEintrag(
        id=f"schatzkiste-nico-{start.strftime('%Y%m%d%H%M')}",
        konto_name="Nico",
        erstellt_am=start,
        ort="Celenusklinik Bad Bergzabern",
        text_inhalt=_nico_text_was_ist_passiert(),
        text_in_drei_monaten=(
            "Die notierten Wuensche lesen, einen ruhigen Ort auswaehlen, "
            "dabei filmen und das Video in die ADHS Gruppe stellen."
        ),
        oeffnen_am=_plus_monate(start, 3),
        kalender_symbol=_KALENDER_SYMBOL_STANDARD,
        kalender_titel_start=start_titel,
        kalender_titel_oeffnen=oeffnen_titel,
        nach_schliessen_gesperrt=True,
    )


def nico_start_eintrag_sicherstellen() -> None:
    """Legt den ersten Nico-Eintrag einmalig an und markiert beide Zeitpunkte im Kalender."""
    zeilen = _roh_laden()
    if any(str(z.get("id", "")) == "schatzkiste-nico-202604091715" for z in zeilen):
        return
    eintrag = _nico_start_eintrag()
    zeilen.append(_als_roh(eintrag))
    _roh_speichern(zeilen)

    # Startmoment (Einlegen) im Kalender markieren.
    einfuegen_wenn_fehlt(
        start=eintrag.erstellt_am,
        ende=eintrag.erstellt_am + dt.timedelta(minutes=10),
        titel=eintrag.kalender_titel_start,
    )
    # Oeffnungstermin in drei Monaten ebenfalls markieren.
    einfuegen_wenn_fehlt(
        start=eintrag.oeffnen_am,
        ende=eintrag.oeffnen_am + dt.timedelta(minutes=10),
        titel=eintrag.kalender_titel_oeffnen,
    )


def eintrag_hinzufuegen(
    *,
    konto_name: str,
    erstellt_am: dt.datetime,
    ort: str,
    text_inhalt: str,
    text_in_drei_monaten: str,
    kalender_symbol: str = _KALENDER_SYMBOL_STANDARD,
) -> SchatzkistenEintrag:
    """Fuer spaetere UI-Dialoge: einen neuen Schatzkisten-Eintrag speichern."""
    if erstellt_am.tzinfo is None:
        erstellt_am = erstellt_am.replace(tzinfo=_TZ_BERLIN)
    eintrag = SchatzkistenEintrag(
        id=str(uuid.uuid4()),
        konto_name=konto_name.strip(),
        erstellt_am=erstellt_am,
        ort=ort.strip(),
        text_inhalt=text_inhalt.strip(),
        text_in_drei_monaten=text_in_drei_monaten.strip(),
        oeffnen_am=_plus_monate(erstellt_am, 3),
        kalender_symbol=kalender_symbol,
        kalender_titel_start=f"{kalender_symbol} Schatzkiste befuellt ({konto_name.strip()})",
        kalender_titel_oeffnen=(
            f"{kalender_symbol} Schatzkiste oeffnen ({konto_name.strip()}, Rueckblick nach 3 Monaten)"
        ),
        nach_schliessen_gesperrt=True,
    )
    zeilen = _roh_laden()
    zeilen.append(_als_roh(eintrag))
    _roh_speichern(zeilen)
    einfuegen_wenn_fehlt(
        start=eintrag.erstellt_am,
        ende=eintrag.erstellt_am + dt.timedelta(minutes=10),
        titel=eintrag.kalender_titel_start,
    )
    einfuegen_wenn_fehlt(
        start=eintrag.oeffnen_am,
        ende=eintrag.oeffnen_am + dt.timedelta(minutes=10),
        titel=eintrag.kalender_titel_oeffnen,
    )
    return eintrag
