"""Kleines Sonnen-Icon für die Zeitleiste (tkinter Canvas)."""

from __future__ import annotations

import math
import tkinter as tk


def sonne_zeitleiste_zeichnen(
    c: tk.Canvas,
    cx: float,
    cy: float,
    radius: float,
    *,
    fuell: str,
    strahl: str,
    strahllaenge: float = 3.5,
) -> None:
    """Scheibe mit acht kurzen Strahlen (Strahlen liegen über der Scheibe, nach außen)."""
    r = float(radius)
    rl = float(strahllaenge)
    c.create_oval(
        cx - r,
        cy - r,
        cx + r,
        cy + r,
        fill=fuell,
        outline=strahl,
        width=1,
    )
    for i in range(8):
        w = (i * math.pi) / 4.0
        ca, sa = math.cos(w), math.sin(w)
        x1 = cx + r * ca
        y1 = cy - r * sa
        x2 = cx + (r + rl) * ca
        y2 = cy - (r + rl) * sa
        c.create_line(x1, y1, x2, y2, fill=strahl, width=1)
