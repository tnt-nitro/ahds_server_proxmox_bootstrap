"""Konfigurierbare Kategorie-Hierarchie fuer Kontakte (Stufe 1–3, Datei-basiert)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Historische feste IDs (Kompatibilitaet, Defaults)
_KAT_VERSION = 1
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Aus speicher.py importieren wir nur fuer Default-Bau — Zyklen vermeiden: hier duplizieren wir die Defaults.
_DEFAULT_OBER_IDS: tuple[str, ...] = (
    "medizin",
    "arbeit",
    "arbeitskollegen",
    "nachbarn",
    "vereine",
    "handwerker",
    "telekommunikation",
    "sonstiges",
)
_DEFAULT_MED_UNTER: tuple[tuple[str, str], ...] = (
    ("aerzte", "Ärzte"),
    ("apotheke", "Apotheken"),
    ("krankenhaus", "Krankenhäuser"),
    ("notfall", "Notfallnummern"),
    ("krankenkasse", "Krankenkassen"),
)
_DEFAULT_HW_UNTER: tuple[tuple[str, str], ...] = (
    ("elektriker", "Elektriker"),
    ("dachdecker", "Dachdecker"),
    ("kanalreinigung", "Kanalreinigung"),
    ("tischler", "Tischler"),
    ("hausmeister", "Hausmeister"),
    ("gaertner", "Gärtner"),
    ("sonstiges", "Sonstiges"),
)
_DEFAULT_LABELS: dict[str, str] = {
    "medizin": "Medizin",
    "arbeit": "Arbeit",
    "arbeitskollegen": "Arbeitskollegen",
    "nachbarn": "Nachbarn",
    "vereine": "Vereine",
    "handwerker": "Handwerker",
    "telekommunikation": "Telekommunikation",
    "sonstiges": "Sonstiges",
}


def _datei_pfad() -> Path:
    ziel = Path.home() / "AhDs" / "Adressbuch"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel / "kontakte_kategorien.json"


@dataclass(frozen=True)
class Stufe3Eintrag:
    id: str
    label: str


@dataclass(frozen=True)
class Stufe2Eintrag:
    id: str
    label: str
    stufe3: tuple[Stufe3Eintrag, ...]


@dataclass(frozen=True)
class Stufe1Eintrag:
    id: str
    label: str
    stufe2: tuple[Stufe2Eintrag, ...]


@dataclass(frozen=True)
class KategorieSchema:
    version: int
    stufe1: tuple[Stufe1Eintrag, ...]


def _bau_default_schema() -> KategorieSchema:
    stufe1_list: list[Stufe1Eintrag] = []
    for oid in _DEFAULT_OBER_IDS:
        olabel = _DEFAULT_LABELS.get(oid, oid)
        if oid == "medizin":
            s2 = tuple(
                Stufe2Eintrag(i, lab, ()) for i, lab in _DEFAULT_MED_UNTER
            )
        elif oid == "handwerker":
            s2 = tuple(
                Stufe2Eintrag(i, lab, ()) for i, lab in _DEFAULT_HW_UNTER
            )
        else:
            s2 = ()
        stufe1_list.append(Stufe1Eintrag(oid, olabel, s2))
    return KategorieSchema(version=_KAT_VERSION, stufe1=tuple(stufe1_list))


def _stufe3_aus_roh(roh: object) -> tuple[Stufe3Eintrag, ...]:
    if not isinstance(roh, list):
        return ()
    out: list[Stufe3Eintrag] = []
    for x in roh:
        if not isinstance(x, dict):
            continue
        sid = str(x.get("id", "")).strip()
        lab = str(x.get("label", "")).strip() or sid
        if sid and _SLUG_RE.match(sid):
            out.append(Stufe3Eintrag(id=sid, label=lab))
    return tuple(out)


def _stufe2_aus_roh(roh: object) -> tuple[Stufe2Eintrag, ...]:
    if not isinstance(roh, list):
        return ()
    out: list[Stufe2Eintrag] = []
    for x in roh:
        if not isinstance(x, dict):
            continue
        uid = str(x.get("id", "")).strip()
        lab = str(x.get("label", "")).strip() or uid
        s3 = _stufe3_aus_roh(x.get("stufe3", x.get("unter", [])))
        if uid and _SLUG_RE.match(uid):
            out.append(Stufe2Eintrag(id=uid, label=lab, stufe3=s3))
    return tuple(out)


def _stufe1_aus_roh(roh: object) -> tuple[Stufe1Eintrag, ...]:
    if not isinstance(roh, list):
        return ()
    out: list[Stufe1Eintrag] = []
    for x in roh:
        if not isinstance(x, dict):
            continue
        oid = str(x.get("id", "")).strip()
        lab = str(x.get("label", "")).strip() or oid
        s2 = _stufe2_aus_roh(x.get("stufe2", x.get("unter", [])))
        if oid and _SLUG_RE.match(oid):
            out.append(Stufe1Eintrag(id=oid, label=lab, stufe2=s2))
    return tuple(out)


def schema_aus_dict(roh: dict[str, object]) -> KategorieSchema | None:
    v = int(roh.get("version", 1))
    s1 = _stufe1_aus_roh(roh.get("stufe1", roh.get("ober", [])))
    if not s1:
        return None
    return KategorieSchema(version=v, stufe1=s1)


def schema_zu_dict(schema: KategorieSchema) -> dict[str, object]:
    def s3_dict(z: Stufe3Eintrag) -> dict[str, object]:
        return {"id": z.id, "label": z.label}

    def s2_dict(u: Stufe2Eintrag) -> dict[str, object]:
        return {
            "id": u.id,
            "label": u.label,
            "stufe3": [s3_dict(z) for z in u.stufe3],
        }

    return {
        "version": schema.version,
        "stufe1": [
            {
                "id": o.id,
                "label": o.label,
                "stufe2": [s2_dict(u) for u in o.stufe2],
            }
            for o in schema.stufe1
        ],
    }


_schema_cache: KategorieSchema | None = None


def kategorien_laden() -> KategorieSchema:
    """Laedt Schema aus Datei oder liefert programm-Defaults."""
    pf = _datei_pfad()
    if not pf.is_file():
        return _bau_default_schema()
    try:
        roh = json.loads(pf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _bau_default_schema()
    if not isinstance(roh, dict):
        return _bau_default_schema()
    s = schema_aus_dict(roh)
    return s if s is not None else _bau_default_schema()


def kategorie_schema_cache() -> KategorieSchema:
    """Gecachtes Schema (nach Dateiwechsel ``kategorie_schema_leeren`` aufrufen)."""
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = kategorien_laden()
    return _schema_cache


def kategorie_schema_leeren() -> None:
    global _schema_cache
    _schema_cache = None


def kategorien_speichern(schema: KategorieSchema) -> None:
    pf = _datei_pfad()
    pf.write_text(
        json.dumps(schema_zu_dict(schema), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    kategorie_schema_leeren()


def ober_nach_id(schema: KategorieSchema, ober_id: str) -> Stufe1Eintrag | None:
    oid = ober_id.strip()
    for o in schema.stufe1:
        if o.id == oid:
            return o
    return None


def stufe2_nach_id(o: Stufe1Eintrag, uid: str) -> Stufe2Eintrag | None:
    u = uid.strip()
    for x in o.stufe2:
        if x.id == u:
            return x
    return None


def hat_stufe2(ober: Stufe1Eintrag) -> bool:
    return len(ober.stufe2) > 0


def hat_stufe3(st2: Stufe2Eintrag) -> bool:
    return len(st2.stufe3) > 0


def norm_kontakt_kategorien(
    schema: KategorieSchema,
    kategorie_haupt: str,
    kategorie_unter: str,
    kategorie_detail: str,
) -> tuple[str, str, str]:
    """Validiert und normalisiert (kh, ku, kd) gegen das Schema."""
    kh = kategorie_haupt.strip()
    ku = kategorie_unter.strip()
    kd = kategorie_detail.strip()
    o = ober_nach_id(schema, kh)
    if o is None:
        fallback = schema.stufe1[0] if schema.stufe1 else None
        if fallback is None:
            return "medizin", "aerzte", ""
        return norm_kontakt_kategorien(schema, fallback.id, "", "")
    if not hat_stufe2(o):
        return o.id, "", ""
    u = stufe2_nach_id(o, ku)
    if u is None:
        u = o.stufe2[0]
    if not hat_stufe3(u):
        return o.id, u.id, ""
    z = kd
    erlaubt = {z.id for z in u.stufe3}
    if z not in erlaubt and u.stufe3:
        z = u.stufe3[0].id
    return o.id, u.id, z


def label_stufe1(schema: KategorieSchema, oid: str) -> str:
    o = ober_nach_id(schema, oid)
    return o.label if o else oid


def label_stufe2(schema: KategorieSchema, oid: str, uid: str) -> str:
    o = ober_nach_id(schema, oid)
    if o is None:
        return uid
    u = stufe2_nach_id(o, uid)
    return u.label if u else uid


def label_stufe3(_schema: KategorieSchema, oid: str, uid: str, did: str) -> str:
    o = ober_nach_id(_schema, oid)
    if o is None:
        return did
    u = stufe2_nach_id(o, uid)
    if u is None:
        return did
    for z in u.stufe3:
        if z.id == did:
            return z.label
    return did


def braucht_fachrichtung(kh: str, ku: str) -> bool:
    """Ärzte-Fachrichtung: feste ID aerzte unter medizin."""
    return kh == "medizin" and ku == "aerzte"


def migration_aus_legacy(
    kh: str,
    ku: str,
    kd: str,
) -> tuple[str, str, str]:
    """Wandelt alte Speicherform (allgemein + detail) in neue Form."""
    kh = kh.strip() or "medizin"
    ku = (ku or "").strip()
    kd = (kd or "").strip()
    if kh == "handwerker" and ku == "allgemein" and kd:
        return kh, kd, ""
    if ku == "allgemein":
        return kh, "", kd if kd else ""
    return kh, ku, kd


def slug_ist_gueltig(s: str) -> bool:
    return bool(s and _SLUG_RE.match(s.strip()))
