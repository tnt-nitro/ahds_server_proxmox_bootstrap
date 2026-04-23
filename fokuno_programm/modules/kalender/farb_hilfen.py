"""Kleine Farbhilfen für Kalender-UI (z. B. Hover auf Kopfzeilen)."""

from __future__ import annotations

# Leichtes Abdunkeln der Zeitleistenfarbe bei Mausover (Hell- und Dunkelmodus).
MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR = 0.93


def hex_rgb_mit_faktor(farbe: str, faktor: float) -> str:
    """Multipliziert R/G/B (0–255) mit ``faktor`` (z. B. 0.93 = etwas dunkler)."""
    roh = farbe.strip().lstrip("#")
    if len(roh) != 6:
        return farbe
    try:
        r = int(roh[0:2], 16)
        g = int(roh[2:4], 16)
        b = int(roh[4:6], 16)
    except ValueError:
        return farbe
    r = max(0, min(255, int(round(r * faktor))))
    g = max(0, min(255, int(round(g * faktor))))
    b = max(0, min(255, int(round(b * faktor))))
    return f"#{r:02x}{g:02x}{b:02x}"
