"""Speicherlogik fuer Krankmeldungen."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path


def _datei_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Krankmeldung"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "eintraege.json"


@dataclass(frozen=True)
class KrankmeldungAenderung:
    geaendert_am: dt.datetime
    felder: tuple[str, ...] = ()
    start_datum_alt: dt.date | None = None
    start_datum_neu: dt.date | None = None
    ende_datum_alt: dt.date | None = None
    ende_datum_neu: dt.date | None = None
    wiedervorstellung_datum_alt: dt.date | None = None
    wiedervorstellung_datum_neu: dt.date | None = None


@dataclass(frozen=True)
class KrankmeldungEintrag:
    id: str
    start_datum: dt.date
    ende_datum: dt.date
    wiedervorstellung_datum: dt.date
    arzttermin_art: str
    arzttermin_zeit: str
    arzt_id: str
    arzt_name_snapshot: str
    notiz: str
    dokument_pfad: str
    erstellt_am: dt.datetime
    geaendert_am: dt.datetime
    aenderungsanzahl: int = 0
    aenderungen: tuple[KrankmeldungAenderung, ...] = field(default_factory=tuple)


def _aenderung_aus_roh(zeile: dict[str, object]) -> KrankmeldungAenderung | None:
    try:
        return KrankmeldungAenderung(
            geaendert_am=dt.datetime.fromisoformat(str(zeile["geaendert_am"])),
            felder=tuple(str(wert) for wert in list(zeile.get("felder", []))),
            start_datum_alt=(
                dt.date.fromisoformat(str(zeile["start_datum_alt"]))
                if zeile.get("start_datum_alt")
                else None
            ),
            start_datum_neu=(
                dt.date.fromisoformat(str(zeile["start_datum_neu"]))
                if zeile.get("start_datum_neu")
                else None
            ),
            ende_datum_alt=(
                dt.date.fromisoformat(str(zeile["ende_datum_alt"]))
                if zeile.get("ende_datum_alt")
                else None
            ),
            ende_datum_neu=(
                dt.date.fromisoformat(str(zeile["ende_datum_neu"]))
                if zeile.get("ende_datum_neu")
                else None
            ),
            wiedervorstellung_datum_alt=(
                dt.date.fromisoformat(str(zeile["wiedervorstellung_datum_alt"]))
                if zeile.get("wiedervorstellung_datum_alt")
                else None
            ),
            wiedervorstellung_datum_neu=(
                dt.date.fromisoformat(str(zeile["wiedervorstellung_datum_neu"]))
                if zeile.get("wiedervorstellung_datum_neu")
                else None
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _aenderung_als_roh(aenderung: KrankmeldungAenderung) -> dict[str, object]:
    return {
        "geaendert_am": aenderung.geaendert_am.isoformat(),
        "felder": list(aenderung.felder),
        "start_datum_alt": (
            aenderung.start_datum_alt.isoformat()
            if aenderung.start_datum_alt is not None
            else ""
        ),
        "start_datum_neu": (
            aenderung.start_datum_neu.isoformat()
            if aenderung.start_datum_neu is not None
            else ""
        ),
        "ende_datum_alt": (
            aenderung.ende_datum_alt.isoformat()
            if aenderung.ende_datum_alt is not None
            else ""
        ),
        "ende_datum_neu": (
            aenderung.ende_datum_neu.isoformat()
            if aenderung.ende_datum_neu is not None
            else ""
        ),
        "wiedervorstellung_datum_alt": (
            aenderung.wiedervorstellung_datum_alt.isoformat()
            if aenderung.wiedervorstellung_datum_alt is not None
            else ""
        ),
        "wiedervorstellung_datum_neu": (
            aenderung.wiedervorstellung_datum_neu.isoformat()
            if aenderung.wiedervorstellung_datum_neu is not None
            else ""
        ),
    }


def _aus_roh(zeile: dict[str, object]) -> KrankmeldungEintrag | None:
    try:
        erstellt_am = dt.datetime.fromisoformat(str(zeile["erstellt_am"]))
        geaendert_am_roh = str(zeile.get("geaendert_am", "")).strip()
        geaendert_am = (
            dt.datetime.fromisoformat(geaendert_am_roh)
            if geaendert_am_roh
            else erstellt_am
        )
        aenderungen_roh = list(zeile.get("aenderungen", []))
        aenderungen: list[KrankmeldungAenderung] = []
        for aenderung_roh in aenderungen_roh:
            if isinstance(aenderung_roh, dict):
                aenderung = _aenderung_aus_roh(aenderung_roh)
                if aenderung is not None:
                    aenderungen.append(aenderung)
        return KrankmeldungEintrag(
            id=str(zeile["id"]),
            start_datum=dt.date.fromisoformat(str(zeile["start_datum"])),
            ende_datum=dt.date.fromisoformat(str(zeile["ende_datum"])),
            wiedervorstellung_datum=dt.date.fromisoformat(
                str(zeile["wiedervorstellung_datum"])
            ),
            arzttermin_art=str(zeile.get("arzttermin_art", "wiedervorstellung")).strip()
            or "wiedervorstellung",
            arzttermin_zeit=str(zeile.get("arzttermin_zeit", "09:00")).strip() or "09:00",
            arzt_id=str(zeile.get("arzt_id", "")).strip(),
            arzt_name_snapshot=str(zeile.get("arzt_name_snapshot", "")).strip(),
            notiz=str(zeile.get("notiz", "")).strip(),
            dokument_pfad=str(zeile.get("dokument_pfad", "")).strip(),
            erstellt_am=erstellt_am,
            geaendert_am=geaendert_am,
            aenderungsanzahl=max(
                int(zeile.get("aenderungsanzahl", len(aenderungen))),
                len(aenderungen),
            ),
            aenderungen=tuple(aenderungen),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _als_roh(eintrag: KrankmeldungEintrag) -> dict[str, object]:
    return {
        "id": eintrag.id,
        "start_datum": eintrag.start_datum.isoformat(),
        "ende_datum": eintrag.ende_datum.isoformat(),
        "wiedervorstellung_datum": eintrag.wiedervorstellung_datum.isoformat(),
        "arzttermin_art": eintrag.arzttermin_art,
        "arzttermin_zeit": eintrag.arzttermin_zeit,
        "arzt_id": eintrag.arzt_id,
        "arzt_name_snapshot": eintrag.arzt_name_snapshot,
        "notiz": eintrag.notiz,
        "dokument_pfad": eintrag.dokument_pfad,
        "erstellt_am": eintrag.erstellt_am.isoformat(),
        "geaendert_am": eintrag.geaendert_am.isoformat(),
        "aenderungsanzahl": eintrag.aenderungsanzahl,
        "aenderungen": [_aenderung_als_roh(a) for a in eintrag.aenderungen],
    }


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


def alle_eintraege() -> list[KrankmeldungEintrag]:
    out: list[KrankmeldungEintrag] = []
    for zeile in _roh_laden():
        eintrag = _aus_roh(zeile)
        if eintrag is not None:
            out.append(eintrag)
    return sorted(out, key=lambda e: (e.ende_datum, e.wiedervorstellung_datum))


def eintrag_mit_id(eintrag_id: str) -> KrankmeldungEintrag | None:
    for eintrag in alle_eintraege():
        if eintrag.id == eintrag_id:
            return eintrag
    return None


def eintrag_fuer_tag(tag: dt.date) -> KrankmeldungEintrag | None:
    kandidaten = [e for e in alle_eintraege() if e.start_datum <= tag <= e.ende_datum]
    if not kandidaten:
        return None
    return min(
        kandidaten,
        key=lambda e: (
            e.ende_datum,
            e.wiedervorstellung_datum,
            -e.geaendert_am.timestamp(),
        ),
    )


def ist_krankgeschrieben_am(tag: dt.date) -> bool:
    """True, wenn ``tag`` in einem Krankmeldungszeitraum liegt."""
    return eintrag_fuer_tag(tag) is not None


def ist_wiedervorstellung_am(tag: dt.date) -> bool:
    """True, wenn an ``tag`` eine Wiedervorstellung beim Arzt eingetragen ist."""
    for eintrag in alle_eintraege():
        if eintrag.wiedervorstellung_datum == tag:
            return True
    return False


def eintrag_hinzufuegen(
    *,
    start_datum: dt.date,
    ende_datum: dt.date,
    wiedervorstellung_datum: dt.date,
    arzttermin_art: str = "wiedervorstellung",
    arzttermin_zeit: str = "09:00",
    arzt_id: str = "",
    arzt_name_snapshot: str = "",
    notiz: str = "",
    dokument_pfad: str = "",
) -> KrankmeldungEintrag:
    jetzt = dt.datetime.now()
    eintrag = KrankmeldungEintrag(
        id=str(uuid.uuid4()),
        start_datum=start_datum,
        ende_datum=ende_datum,
        wiedervorstellung_datum=wiedervorstellung_datum,
        arzttermin_art=arzttermin_art.strip() or "wiedervorstellung",
        arzttermin_zeit=arzttermin_zeit.strip() or "09:00",
        arzt_id=arzt_id.strip(),
        arzt_name_snapshot=arzt_name_snapshot.strip(),
        notiz=notiz.strip(),
        dokument_pfad=dokument_pfad.strip(),
        erstellt_am=jetzt,
        geaendert_am=jetzt,
    )
    zeilen = _roh_laden()
    zeilen.append(_als_roh(eintrag))
    _roh_speichern(zeilen)
    return eintrag


def eintrag_aktualisieren(
    eintrag_id: str,
    *,
    start_datum: dt.date,
    ende_datum: dt.date,
    wiedervorstellung_datum: dt.date,
    arzttermin_art: str = "wiedervorstellung",
    arzttermin_zeit: str = "09:00",
    arzt_id: str = "",
    arzt_name_snapshot: str = "",
    notiz: str = "",
    dokument_pfad: str = "",
) -> KrankmeldungEintrag | None:
    zeilen = _roh_laden()
    jetzt = dt.datetime.now()
    for index, zeile in enumerate(zeilen):
        if str(zeile.get("id", "")) != eintrag_id:
            continue
        alt = _aus_roh(zeile)
        if alt is None:
            return None
        geaenderte_felder: list[str] = []
        if alt.start_datum != start_datum:
            geaenderte_felder.append("start_datum")
        if alt.ende_datum != ende_datum:
            geaenderte_felder.append("ende_datum")
        if alt.wiedervorstellung_datum != wiedervorstellung_datum:
            geaenderte_felder.append("wiedervorstellung_datum")
        if alt.arzttermin_art != (arzttermin_art.strip() or "wiedervorstellung"):
            geaenderte_felder.append("arzttermin_art")
        if alt.arzttermin_zeit != (arzttermin_zeit.strip() or "09:00"):
            geaenderte_felder.append("arzttermin_zeit")
        if alt.arzt_id != arzt_id.strip():
            geaenderte_felder.append("arzt_id")
        if alt.arzt_name_snapshot != arzt_name_snapshot.strip():
            geaenderte_felder.append("arzt_name_snapshot")
        if alt.notiz != notiz.strip():
            geaenderte_felder.append("notiz")
        if alt.dokument_pfad != dokument_pfad.strip():
            geaenderte_felder.append("dokument_pfad")

        aenderungen = list(alt.aenderungen)
        aenderungsanzahl = alt.aenderungsanzahl
        geaendert_am = alt.geaendert_am
        if geaenderte_felder:
            aenderungen.append(
                KrankmeldungAenderung(
                    geaendert_am=jetzt,
                    felder=tuple(geaenderte_felder),
                    start_datum_alt=alt.start_datum,
                    start_datum_neu=start_datum,
                    ende_datum_alt=alt.ende_datum,
                    ende_datum_neu=ende_datum,
                    wiedervorstellung_datum_alt=alt.wiedervorstellung_datum,
                    wiedervorstellung_datum_neu=wiedervorstellung_datum,
                )
            )
            aenderungsanzahl += 1
            geaendert_am = jetzt

        neu = KrankmeldungEintrag(
            id=alt.id,
            start_datum=start_datum,
            ende_datum=ende_datum,
            wiedervorstellung_datum=wiedervorstellung_datum,
            arzttermin_art=arzttermin_art.strip() or "wiedervorstellung",
            arzttermin_zeit=arzttermin_zeit.strip() or "09:00",
            arzt_id=arzt_id.strip(),
            arzt_name_snapshot=arzt_name_snapshot.strip(),
            notiz=notiz.strip(),
            dokument_pfad=dokument_pfad.strip(),
            erstellt_am=alt.erstellt_am,
            geaendert_am=geaendert_am,
            aenderungsanzahl=aenderungsanzahl,
            aenderungen=tuple(aenderungen),
        )
        zeilen[index] = _als_roh(neu)
        _roh_speichern(zeilen)
        return neu
    return None


def eintrag_loeschen(eintrag_id: str) -> bool:
    zeilen = _roh_laden()
    neue_zeilen = [zeile for zeile in zeilen if str(zeile.get("id", "")) != eintrag_id]
    if len(neue_zeilen) == len(zeilen):
        return False
    _roh_speichern(neue_zeilen)
    return True
