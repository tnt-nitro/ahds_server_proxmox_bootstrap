"""Schatzkiste: Platzhalteransicht fuer wichtige, gespeicherte Elemente."""
# nicht löschen !!! 09.04.2026 DIese Zeile nicht löschen oder zu anderen Programmteile der Schatzkiste mitnehmen
from __future__ import annotations

import datetime as dt
import tkinter as tk

from locales import get_string
from modules.schatzkiste.speicher import (
    alle_eintraege,
    nico_start_eintrag_sicherstellen,
)
from modules.theming.farben import kalender_farben


def _fmt_datetime_wert(zeitpunkt: dt.datetime) -> str:
    return zeitpunkt.strftime("%d.%m.%Y - %H:%M Uhr")


def schatzkiste_in(parent: tk.Misc, locale: str = "de") -> None:
    """Baut die Schatzkisten-Ansicht in den uebergebenen Container."""
    nico_start_eintrag_sicherstellen()
    kf = kalender_farben()

    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Label(
        aussen,
        text=get_string("app.schatzkiste.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X)

    tk.Label(
        aussen,
        text=get_string("app.schatzkiste.untertitel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, pady=(6, 0))

    eintraege = alle_eintraege()
    if not eintraege:
        tk.Label(
            aussen,
            text=get_string("app.schatzkiste.status_platzhalter", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 10),
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(12, 0))
        return

    eintrag = sorted(eintraege, key=lambda e: e.erstellt_am)[-1]

    details = [
        get_string("app.schatzkiste.konto", locale).format(konto=eintrag.konto_name),
        get_string("app.schatzkiste.erstellt_am", locale).format(
            zeitpunkt=_fmt_datetime_wert(eintrag.erstellt_am)
        ),
        get_string("app.schatzkiste.ort", locale).format(ort=eintrag.ort),
        get_string("app.schatzkiste.oeffnen_am", locale).format(
            zeitpunkt=_fmt_datetime_wert(eintrag.oeffnen_am)
        ),
        get_string("app.schatzkiste.gesperrt", locale).format(
            status=(
                get_string("app.schatzkiste.status_gesperrt", locale)
                if eintrag.nach_schliessen_gesperrt
                else get_string("app.schatzkiste.status_offen", locale)
            )
        ),
        get_string("app.schatzkiste.kalender_symbol", locale).format(
            symbol=eintrag.kalender_symbol
        ),
        "",
        get_string("app.schatzkiste.was_ist_passiert", locale),
        eintrag.text_inhalt,
        "",
        get_string("app.schatzkiste.in_drei_monaten", locale),
        eintrag.text_in_drei_monaten,
    ]
    tk.Label(
        aussen,
        text="\n".join(details),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, pady=(12, 0))
