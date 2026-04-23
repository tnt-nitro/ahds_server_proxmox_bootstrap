"""Mondscheibe auf ``tk.Canvas`` (Pixelraster)."""

from __future__ import annotations

import math
import tkinter as tk

from .berechnung import mondphase_beleuchtungsanteil

# Unbeleuchtet / Schatten (Neumond)
_FARBE_SCHATTEN: str = "#000000"
# Beleuchtete Fläche inkl. Vollmond: dunkel genug für weiße Schrift (~WCAG mit #FFF)
_FARBE_BELEUCHTET: str = "#F9F9F9"

_NEU_SCHWELLE: float = 0.015
_VOLL_SCHWELLE: float = 0.01


def mondscheibe_zeichnen(
    c: tk.Canvas,
    cx: float,
    cy: float,
    radius: float,
    phase_0_1: float,
    *,
    farbe_beleuchtet: str | None = None,
    farbe_schatten: str | None = None,
) -> None:
    """Zeichnet die Mondphase als gefüllte Kreisscheibe.

    * Neumond: durchgehend schwarz.
    * Vollmond: durchgehend dunkles Grau (``farbe_beleuchtet``).
    * Dazwischen: beleuchtete Seite in Grau, Schatten schwarz.
    """
    licht = farbe_beleuchtet or _FARBE_BELEUCHTET
    schatten = farbe_schatten or _FARBE_SCHATTEN

    p = phase_0_1 % 1.0
    if p < _NEU_SCHWELLE or p > 1.0 - _NEU_SCHWELLE:
        _scheibe_einfarbig(c, cx, cy, radius, schatten)
        return
    if abs(p - 0.5) < _VOLL_SCHWELLE:
        _scheibe_einfarbig(c, cx, cy, radius, licht)
        return

    k = mondphase_beleuchtungsanteil(p)
    waxing = p < 0.5
    r = float(radius)
    r2 = r * r

    xi0 = int(math.floor(cx - r - 1))
    xi1 = int(math.ceil(cx + r + 1))
    yi0 = int(math.floor(cy - r - 1))
    yi1 = int(math.ceil(cy + r + 1))

    for xi in range(xi0, xi1 + 1):
        for yi in range(yi0, yi1 + 1):
            dx = float(xi) + 0.5 - cx
            dy = float(yi) + 0.5 - cy
            if dx * dx + dy * dy > r2:
                continue
            if waxing:
                beleuchtet = dx >= r * (1.0 - 2.0 * k)
            else:
                beleuchtet = dx <= r * (2.0 * k - 1.0)
            farbe = licht if beleuchtet else schatten
            c.create_rectangle(
                xi, yi, xi + 1, yi + 1, fill=farbe, width=0, outline=farbe
            )


def _scheibe_einfarbig(
    c: tk.Canvas, cx: float, cy: float, radius: float, farbe: str
) -> None:
    r = float(radius)
    c.create_oval(
        cx - r,
        cy - r,
        cx + r,
        cy + r,
        fill=farbe,
        outline=farbe,
        width=1,
    )
