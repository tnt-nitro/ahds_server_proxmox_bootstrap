"""Schneller Umschalt zwischen hellem und dunklem Erscheinungsbild (globaler Prozesszustand)."""

from __future__ import annotations

from enum import Enum


class Erscheinungsmodus(Enum):
    NORMAL = "normal"
    DARK = "dark"


_modus: Erscheinungsmodus = Erscheinungsmodus.NORMAL


def aktueller_modus() -> Erscheinungsmodus:
    return _modus


def ist_darkmode() -> bool:
    return _modus is Erscheinungsmodus.DARK


def setze_modus(modus: Erscheinungsmodus) -> None:
    """Setzt den Modus (z. B. nach Nutzerwahl oder gespeicherter Einstellung)."""
    global _modus
    _modus = modus


def toggle_modus() -> Erscheinungsmodus:
    """Wechselt Normal ↔ Dark und gibt den neuen Modus zurück."""
    neu = (
        Erscheinungsmodus.NORMAL
        if ist_darkmode()
        else Erscheinungsmodus.DARK
    )
    setze_modus(neu)
    return neu
