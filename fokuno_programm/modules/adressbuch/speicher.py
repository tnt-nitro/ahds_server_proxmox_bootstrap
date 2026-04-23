"""Speicherlogik fuer Kontakte (Lebensbereiche, Medizin-Detail, Ansprechpartner)."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from .kategorie_konfig import (
    kategorie_schema_cache,
    migration_aus_legacy,
    norm_kontakt_kategorien,
)

# Fachrichtungen unter „Ärzte“ (erweiterbar).
STANDARD_FACHRICHTUNGEN: tuple[str, ...] = (
    "Hausarzt",
    "Zahnarzt",
    "Psychologe",
    "Psychotherapeut",
    "Dermatologe",
    "HNO",
    "Kardiologe",
    "Augenarzt",
    "Hautarzt",
    "Gynaekologe",
    "Urologe",
    "Orthopaede",
    "Neurologe",
    "Kinderarzt",
    "Sonstiges",
)

# Oberkategorie (Lebensbereich) – Schluessel in JSON.
LEBENSBEREICH_IDS: tuple[str, ...] = (
    "medizin",
    "arbeit",
    "arbeitskollegen",
    "nachbarn",
    "vereine",
    "handwerker",
    "telekommunikation",
    "sonstiges",
)

# Unterkategorie nur innerhalb „Medizin“.
KATEGORIE_UNTER_IDS: tuple[str, ...] = (
    "aerzte",
    "apotheke",
    "krankenhaus",
    "notfall",
    "krankenkasse",
)

# Platzhalter fuer Kontakte ausserhalb Medizin (ein Satz, kein weiteres Raster).
KATEGORIE_UNTER_ALLGEMEIN: str = "allgemein"

# Untertypen bei Lebensbereich „Handwerker“.
HANDWERKER_DETAIL_IDS: tuple[str, ...] = (
    "elektriker",
    "dachdecker",
    "kanalreinigung",
    "tischler",
    "hausmeister",
    "gaertner",
    "sonstiges",
)


@dataclass(frozen=True)
class AnsprechpartnerEintrag:
    """Eine Person/Rolle bei einem Betrieb (z. B. Verkauf, Werkstatt)."""

    rolle: str
    name: str
    telefon: str
    email: str
    notiz: str


def _datei_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Adressbuch"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "kontakte_aerzte.json"


def _letzter_kontakt_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Kontakte"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "letzter_kontakt.json"


def _letzter_kontakt_roh() -> dict[str, object]:
    pf = _letzter_kontakt_pfad()
    if not pf.is_file():
        return {}
    try:
        roh = json.loads(pf.read_text(encoding="utf-8"))
        return dict(roh) if isinstance(roh, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def letzter_kontakt_genutzt_id_laden() -> str | None:
    """Zuletzt in der Oberflaeche gewaehlter/angesehener Kontakt."""
    roh = _letzter_kontakt_roh()
    sid = str(roh.get("kontakt_genutzt_id", roh.get("kontakt_id", ""))).strip()
    return sid or None


def letzter_kontakt_gespeichert_id_laden() -> str | None:
    """Zuletzt per Speichern geschriebener Kontakt."""
    roh = _letzter_kontakt_roh()
    sid = str(roh.get("kontakt_gespeichert_id", roh.get("kontakt_id", ""))).strip()
    return sid or None


def letzter_kontakt_genutzt_id_speichern(kontakt_id: str) -> None:
    roh = _letzter_kontakt_roh()
    roh["kontakt_genutzt_id"] = kontakt_id.strip()
    if "kontakt_id" in roh:
        del roh["kontakt_id"]
    _letzter_kontakt_pfad().write_text(
        json.dumps(roh, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def letzter_kontakt_gespeichert_id_speichern(kontakt_id: str) -> None:
    roh = _letzter_kontakt_roh()
    roh["kontakt_gespeichert_id"] = kontakt_id.strip()
    if "kontakt_id" in roh:
        del roh["kontakt_id"]
    _letzter_kontakt_pfad().write_text(
        json.dumps(roh, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass(frozen=True)
class ArztKontakt:
    id: str
    titel: str
    name: str
    fachrichtung: str
    telefon: str
    email: str
    adresse: str
    notiz: str
    erstellt_am: dt.datetime
    geaendert_am: dt.datetime
    favorit: bool
    kategorie_haupt: str
    kategorie_unter: str
    kategorie_detail: str
    verknuepfung_id: str
    kundennummer: str
    ansprechpartner: tuple[AnsprechpartnerEintrag, ...]

    def anzeige_name(self) -> str:
        if self.titel:
            return f"{self.titel} {self.name}".strip()
        return self.name


def _ansprech_aus_liste(roh: object) -> tuple[AnsprechpartnerEintrag, ...]:
    if not isinstance(roh, list):
        return ()
    out: list[AnsprechpartnerEintrag] = []
    for zeile in roh:
        if not isinstance(zeile, dict):
            continue
        out.append(
            AnsprechpartnerEintrag(
                rolle=str(zeile.get("rolle", "")).strip(),
                name=str(zeile.get("name", "")).strip(),
                telefon=str(zeile.get("telefon", "")).strip(),
                email=str(zeile.get("email", "")).strip(),
                notiz=str(zeile.get("notiz", "")).strip(),
            )
        )
    return tuple(out)


def _aus_roh(zeile: dict[str, object]) -> ArztKontakt | None:
    try:
        erstellt = dt.datetime.fromisoformat(str(zeile["erstellt_am"]))
        geaendert_roh = str(zeile.get("geaendert_am", "")).strip()
        geaendert = dt.datetime.fromisoformat(geaendert_roh) if geaendert_roh else erstellt
        kh = str(zeile.get("kategorie_haupt", "medizin")).strip() or "medizin"
        ku = str(zeile.get("kategorie_unter", "aerzte")).strip()
        kd = str(zeile.get("kategorie_detail", "")).strip()
        kh, ku, kd = migration_aus_legacy(kh, ku, kd)
        schema = kategorie_schema_cache()
        kh, ku, kd = norm_kontakt_kategorien(schema, kh, ku, kd)
        return ArztKontakt(
            id=str(zeile["id"]),
            titel=str(zeile.get("titel", "")).strip(),
            name=str(zeile["name"]).strip(),
            fachrichtung=str(zeile.get("fachrichtung", "")).strip(),
            telefon=str(zeile.get("telefon", "")).strip(),
            email=str(zeile.get("email", "")).strip(),
            adresse=str(zeile.get("adresse", "")).strip(),
            notiz=str(zeile.get("notiz", "")).strip(),
            erstellt_am=erstellt,
            geaendert_am=geaendert,
            favorit=bool(zeile.get("favorit", False)),
            kategorie_haupt=kh,
            kategorie_unter=ku,
            kategorie_detail=kd,
            verknuepfung_id=str(zeile.get("verknuepfung_id", "")).strip(),
            kundennummer=str(zeile.get("kundennummer", "")).strip(),
            ansprechpartner=_ansprech_aus_liste(zeile.get("ansprechpartner")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _als_roh(kontakt: ArztKontakt) -> dict[str, object]:
    ap = [
        {
            "rolle": a.rolle,
            "name": a.name,
            "telefon": a.telefon,
            "email": a.email,
            "notiz": a.notiz,
        }
        for a in kontakt.ansprechpartner
    ]
    return {
        "id": kontakt.id,
        "titel": kontakt.titel,
        "name": kontakt.name,
        "fachrichtung": kontakt.fachrichtung,
        "telefon": kontakt.telefon,
        "email": kontakt.email,
        "adresse": kontakt.adresse,
        "notiz": kontakt.notiz,
        "erstellt_am": kontakt.erstellt_am.isoformat(),
        "geaendert_am": kontakt.geaendert_am.isoformat(),
        "favorit": kontakt.favorit,
        "kategorie_haupt": kontakt.kategorie_haupt,
        "kategorie_unter": kontakt.kategorie_unter,
        "kategorie_detail": kontakt.kategorie_detail,
        "verknuepfung_id": kontakt.verknuepfung_id,
        "kundennummer": kontakt.kundennummer,
        "ansprechpartner": ap,
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


def alle_aerzte() -> list[ArztKontakt]:
    out: list[ArztKontakt] = []
    for zeile in _roh_laden():
        eintrag = _aus_roh(zeile)
        if eintrag is not None:
            out.append(eintrag)
    return sorted(
        out,
        key=lambda e: (
            not e.favorit,
            e.kategorie_haupt.lower(),
            e.kategorie_unter.lower(),
            (e.kategorie_detail or "").lower(),
            (e.fachrichtung or "").lower(),
            e.name.lower(),
        ),
    )


def alle_favoriten() -> list[ArztKontakt]:
    return [k for k in alle_aerzte() if k.favorit]


def arzt_mit_id(arzt_id: str) -> ArztKontakt | None:
    for eintrag in alle_aerzte():
        if eintrag.id == arzt_id:
            return eintrag
    return None


def _norm_kategorie(
    kategorie_haupt: str,
    kategorie_unter: str,
    kategorie_detail: str = "",
) -> tuple[str, str, str]:
    schema = kategorie_schema_cache()
    return norm_kontakt_kategorien(
        schema,
        kategorie_haupt.strip(),
        kategorie_unter.strip(),
        kategorie_detail.strip(),
    )


def arzt_hinzufuegen(
    *,
    titel: str = "",
    name: str,
    fachrichtung: str,
    telefon: str = "",
    email: str = "",
    adresse: str = "",
    notiz: str = "",
    favorit: bool = False,
    kategorie_haupt: str = "medizin",
    kategorie_unter: str = "aerzte",
    kategorie_detail: str = "",
    verknuepfung_id: str = "",
    kundennummer: str = "",
    ansprechpartner: tuple[AnsprechpartnerEintrag, ...] = (),
) -> ArztKontakt:
    jetzt = dt.datetime.now()
    kh, ku, kd = _norm_kategorie(kategorie_haupt, kategorie_unter, kategorie_detail)
    eintrag = ArztKontakt(
        id=str(uuid.uuid4()),
        titel=titel.strip(),
        name=name.strip(),
        fachrichtung=fachrichtung.strip(),
        telefon=telefon.strip(),
        email=email.strip(),
        adresse=adresse.strip(),
        notiz=notiz.strip(),
        erstellt_am=jetzt,
        geaendert_am=jetzt,
        favorit=bool(favorit),
        kategorie_haupt=kh,
        kategorie_unter=ku,
        kategorie_detail=kd,
        verknuepfung_id=verknuepfung_id.strip(),
        kundennummer=kundennummer.strip(),
        ansprechpartner=ansprechpartner,
    )
    zeilen = _roh_laden()
    zeilen.append(_als_roh(eintrag))
    _roh_speichern(zeilen)
    return eintrag


def arzt_aktualisieren(
    arzt_id: str,
    *,
    titel: str = "",
    name: str,
    fachrichtung: str,
    telefon: str = "",
    email: str = "",
    adresse: str = "",
    notiz: str = "",
    favorit: bool = False,
    kategorie_haupt: str = "medizin",
    kategorie_unter: str = "aerzte",
    kategorie_detail: str = "",
    verknuepfung_id: str = "",
    kundennummer: str = "",
    ansprechpartner: tuple[AnsprechpartnerEintrag, ...] = (),
) -> ArztKontakt | None:
    zeilen = _roh_laden()
    jetzt = dt.datetime.now()
    kh, ku, kd = _norm_kategorie(kategorie_haupt, kategorie_unter, kategorie_detail)
    for index, zeile in enumerate(zeilen):
        if str(zeile.get("id", "")) != arzt_id:
            continue
        alt = _aus_roh(zeile)
        if alt is None:
            return None
        neu = ArztKontakt(
            id=alt.id,
            titel=titel.strip(),
            name=name.strip(),
            fachrichtung=fachrichtung.strip(),
            telefon=telefon.strip(),
            email=email.strip(),
            adresse=adresse.strip(),
            notiz=notiz.strip(),
            erstellt_am=alt.erstellt_am,
            geaendert_am=jetzt,
            favorit=bool(favorit),
            kategorie_haupt=kh,
            kategorie_unter=ku,
            kategorie_detail=kd,
            verknuepfung_id=verknuepfung_id.strip(),
            kundennummer=kundennummer.strip(),
            ansprechpartner=ansprechpartner,
        )
        zeilen[index] = _als_roh(neu)
        _roh_speichern(zeilen)
        return neu
    return None


def arzt_loeschen(arzt_id: str) -> bool:
    zeilen = _roh_laden()
    neue_zeilen = [zeile for zeile in zeilen if str(zeile.get("id", "")) != arzt_id]
    if len(neue_zeilen) == len(zeilen):
        return False
    _roh_speichern(neue_zeilen)
    roh = _letzter_kontakt_roh()
    geaendert = False
    for schluessel in ("kontakt_genutzt_id", "kontakt_gespeichert_id", "kontakt_id"):
        if str(roh.get(schluessel, "")).strip() == arzt_id:
            roh.pop(schluessel, None)
            geaendert = True
    if geaendert and roh:
        try:
            _letzter_kontakt_pfad().write_text(
                json.dumps(roh, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass
    elif geaendert and not roh:
        try:
            _letzter_kontakt_pfad().unlink(missing_ok=True)
        except OSError:
            pass
    return True


def export_aerzte_json(zielpfad: str) -> str:
    ziel = Path(zielpfad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    daten = [_als_roh(k) for k in alle_aerzte()]
    ziel.write_text(json.dumps({"eintraege": daten}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(ziel)
