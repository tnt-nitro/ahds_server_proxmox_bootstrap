"""Hilfsfunktionen fuer Fenstertitel und Startscreen-Buildinfos."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

from locales import get_string

from modules.app_umgebung import app_umgebung_laden
from modules.version_info import VersionInfo

PROJEKTSTART_DATUM = dt.date(2026, 4, 4)


@dataclass(frozen=True)
class SemVerAufloesung:
    """Aufgeloeste Versionsnummer in offiziellen SemVer-Begriffen."""

    major: int
    minor: int
    patch: int


@dataclass(frozen=True)
class StartZaehlerStand:
    """Aufbereitete Startzaehler fuer die aktuelle Version."""

    aktuelle_version: str
    major_starts: int
    minor_starts: int
    patch_starts: int
    starts_je_version: dict[str, int]


def _saubere_basis(basis_titel: str) -> str:
    basis = basis_titel.replace("AhDs", "Working Title AhDs").strip()
    return basis


def zeitstempel_jetzt() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def aufloesung_semver(version: str) -> SemVerAufloesung:
    """Leitet MAJOR.MINOR.PATCH direkt aus der Version ab."""
    teile = version.split(".")
    if len(teile) != 3:
        return SemVerAufloesung(major=0, minor=0, patch=0)
    try:
        return SemVerAufloesung(
            major=int(teile[0]),
            minor=int(teile[1]),
            patch=int(teile[2]),
        )
    except ValueError:
        return SemVerAufloesung(major=0, minor=0, patch=0)


def entwicklungszeit_tage() -> int:
    return (dt.date.today() - PROJEKTSTART_DATUM).days


def _zaehler_datei() -> Path:
    stamm = Path(__file__).resolve().parent.parent
    return stamm / "data" / "version_start_history.json"


def _semver_aus_version(version: str) -> tuple[int, int, int] | None:
    teile = version.split(".")
    if len(teile) != 3:
        return None
    try:
        return (int(teile[0]), int(teile[1]), int(teile[2]))
    except ValueError:
        return None


def startaufruf_zaehlen(version: str) -> StartZaehlerStand:
    """Erhoeht den persistenten Startzaehler und berechnet Major/Minor/Patch-Starts.

    Regeln:
    - Major-Zaehler: summiert alle Starts mit gleicher Major-Version.
    - Minor-Zaehler: summiert alle Starts mit gleicher Major+Minor-Version.
    - Patch-Zaehler: Starts der exakten aktuellen Version.
    """
    pfad = _zaehler_datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    daten: dict[str, object] = {"by_version": {}}
    if pfad.exists():
        try:
            geladen = json.loads(pfad.read_text(encoding="utf-8"))
            if isinstance(geladen, dict):
                daten = geladen
        except (json.JSONDecodeError, OSError):
            daten = {"by_version": {}}

    by_version = daten.get("by_version", {})
    if not isinstance(by_version, dict):
        by_version = {}
    version_count = int(by_version.get(version, 0)) + 1
    by_version[version] = version_count

    neu = {"by_version": by_version}
    pfad.write_text(json.dumps(neu, ensure_ascii=True, indent=2), encoding="utf-8")

    semver = _semver_aus_version(version)
    major_starts = version_count
    minor_starts = version_count
    patch_starts = version_count

    if semver is not None:
        major, minor, _patch = semver
        major_starts = 0
        minor_starts = 0
        for version_key, count in by_version.items():
            version_key_str = str(version_key)
            parsed = _semver_aus_version(version_key_str)
            if parsed is None:
                continue
            k_major, k_minor, _k_patch = parsed
            count_int = int(count)
            if k_major == major:
                major_starts += count_int
            if k_major == major and k_minor == minor:
                minor_starts += count_int
        patch_starts = version_count

    starts_je_version = {str(k): int(v) for k, v in by_version.items()}
    return StartZaehlerStand(
        aktuelle_version=version,
        major_starts=major_starts,
        minor_starts=minor_starts,
        patch_starts=patch_starts,
        starts_je_version=starts_je_version,
    )


def _build_kennung_fuer_fenster(locale: str | None) -> str:
    u = app_umgebung_laden()
    return get_string(f"programm.umgebung_build.{u}", locale)


def fenster_titel(
    *,
    basis_titel: str,
    version_info: VersionInfo,
    benutzer: str,
    geoeffnet_um: str,
    locale: str | None = None,
) -> str:
    basis = _saubere_basis(basis_titel)
    build = _build_kennung_fuer_fenster(locale)
    return (
        f"{basis} | {build} | v{version_info.version} | "
        f"User: {benutzer} | Opened: {geoeffnet_um}"
    )


def startscreen_english_block(
    version_info: VersionInfo,
    aufruf_zeit: str,
    start_counter: StartZaehlerStand,
    *,
    locale: str | None = None,
) -> str:
    """Englische Satzkette mit Versionsdaten fuer den Startscreen."""
    semver = aufloesung_semver(version_info.version)
    um = app_umgebung_laden()
    deployment_zeile = get_string("programm.deployment_hinweis", locale).format(env=um)
    return (
        "Working Title: AhDs\n"
        f"Current version: v{version_info.version}\n"
        f"Version created: {version_info.bumped_at or '-'}\n"
        f"Invocation date: {aufruf_zeit}\n"
        f"Project start date: {PROJEKTSTART_DATUM.isoformat()}\n"
        f"Development time in days: {entwicklungszeit_tage()}\n"
        f"{deployment_zeile}\n\n"
        "Resolved version (Semantic Versioning):\n"
        f"MAJOR: {semver.major}\n"
        f"MINOR: {semver.minor}\n"
        f"PATCH: {semver.patch}\n\n"
        "Counter (start invocations):\n"
        f"Major: {semver.major}.x.x -> started {start_counter.major_starts} times\n"
        f"Minor: {semver.major}.{semver.minor}.x -> started {start_counter.minor_starts} times\n"
        f"Patch: {semver.major}.{semver.minor}.{semver.patch} -> started {start_counter.patch_starts} times"
    )
