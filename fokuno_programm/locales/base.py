"""Zentraler Zugriff auf UI-Texte (Schlüssel → Sprache). Fallback: Deutsch."""

from __future__ import annotations

from typing import Final

from . import de, en, fr

_DEFAULT: Final[str] = "de"
_FALLBACK_CHAIN: Final[tuple[str, ...]] = ("de", "en", "fr")

_REGISTRY: Final[dict[str, dict[str, str]]] = {
    "de": de.STRINGS,
    "en": en.STRINGS,
    "fr": fr.STRINGS,
}


def resolve_locale(gewuenscht: str | None) -> str:
    if gewuenscht and gewuenscht in _REGISTRY:
        return gewuenscht
    return _DEFAULT


def get_string(schluessel: str, locale: str | None = None) -> str:
    """Liefert den Text für schluessel; Fallback über Kette _FALLBACK_CHAIN."""
    start = resolve_locale(locale)
    for code in (start, *[c for c in _FALLBACK_CHAIN if c != start]):
        tabelle = _REGISTRY.get(code)
        if tabelle and schluessel in tabelle:
            return tabelle[schluessel]
    return schluessel
