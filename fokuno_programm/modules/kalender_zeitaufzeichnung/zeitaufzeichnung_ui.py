"""UI: Aufnahme Start/Stopp, Einfügen in den Kalender (lokale Zeitblöcke)."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from tkinter import messagebox
from zoneinfo import ZoneInfo

from locales import get_string
from modules.kalender.zeitaufzeichnung_speicher import einfuegen
from modules.sonnenzeit.standort import standard_frankfurt_am_main
from modules.theming.farben import kalender_farben


def zeitaufzeichnung_kalender_in(parent: tk.Misc, locale: str = "de") -> None:
    root = parent.winfo_toplevel()
    kf = kalender_farben()
    tz = ZoneInfo(standard_frankfurt_am_main().zeitzone)

    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Label(
        aussen,
        text=get_string("app.zeitaufzeichnung.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
    ).pack(anchor=tk.W)

    tk.Label(
        aussen,
        text=get_string("app.zeitaufzeichnung.beschreibung", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(4, 12))

    status = tk.Label(
        aussen,
        text=get_string("app.zeitaufzeichnung.status_bereit", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        justify=tk.LEFT,
    )
    status.pack(anchor=tk.W, pady=(0, 8))

    def btn_style() -> dict[str, object]:
        k = kalender_farben()
        return {
            "bg": k.HINTERGRUND_ZEITLEISTE,
            "fg": k.TEXT_ZEIT,
            "activebackground": k.RASTER_STUNDE,
            "activeforeground": k.TEXT_ZEIT,
            "font": ("Segoe UI", 10),
            "relief": tk.FLAT,
            "padx": 12,
            "pady": 6,
        }

    start_zeit: list[dt.datetime | None] = [None]
    ende_zeit: list[dt.datetime | None] = [None]
    tick_id: list[str | None] = [None]

    titel_var = tk.StringVar(
        value=get_string("app.zeitaufzeichnung.titel_standard", locale)
    )
    titel_zeile = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    titel_zeile.pack(anchor=tk.W, pady=(0, 8))
    tk.Label(
        titel_zeile,
        text=get_string("app.zeitaufzeichnung.label_bezeichnung", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
    ).pack(side=tk.LEFT, padx=(0, 8))
    titel_entry = tk.Entry(
        titel_zeile,
        textvariable=titel_var,
        width=36,
        font=("Segoe UI", 10),
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        insertbackground=kf.TEXT_ZEIT,
    )
    titel_entry.pack(side=tk.LEFT)

    def dauer_text(von: dt.datetime, bis: dt.datetime) -> str:
        sec = int((bis - von).total_seconds())
        if sec < 0:
            return "—"
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f"{h:d}:{m:02d}:{s:02d}"

    def tick_entfernen() -> None:
        if tick_id[0] is not None:
            try:
                root.after_cancel(tick_id[0])
            except tk.TclError:
                pass
            tick_id[0] = None

    def tick() -> None:
        a = start_zeit[0]
        if a is None or ende_zeit[0] is not None:
            tick_entfernen()
            return
        jetzt = dt.datetime.now(tz)
        status.configure(
            text=get_string("app.zeitaufzeichnung.status_laufend", locale).format(
                start=a.strftime("%Y-%m-%d %H:%M:%S"),
                dauer=dauer_text(a, jetzt),
            )
        )
        tick_id[0] = root.after(500, tick)

    def start_klick() -> None:
        ende_zeit[0] = None
        start_zeit[0] = dt.datetime.now(tz)
        b_start.configure(state=tk.DISABLED)
        b_stop.configure(state=tk.NORMAL)
        b_einfuegen.configure(state=tk.DISABLED)
        tick_entfernen()
        tick_id[0] = root.after(200, tick)
        status.configure(
            text=get_string("app.zeitaufzeichnung.status_gestartet", locale).format(
                zeit=start_zeit[0].strftime("%Y-%m-%d %H:%M:%S")
            )
        )

    def stop_klick() -> None:
        tick_entfernen()
        a = start_zeit[0]
        if a is None:
            return
        b = dt.datetime.now(tz)
        ende_zeit[0] = b
        b_start.configure(state=tk.NORMAL)
        b_stop.configure(state=tk.DISABLED)
        b_einfuegen.configure(state=tk.NORMAL)
        if b <= a:
            status.configure(text=get_string("app.zeitaufzeichnung.status_zu_kurz", locale))
            ende_zeit[0] = None
            b_einfuegen.configure(state=tk.DISABLED)
            return
        status.configure(
            text=get_string("app.zeitaufzeichnung.status_beendet", locale).format(
                start=a.strftime("%H:%M:%S"),
                ende=b.strftime("%H:%M:%S"),
                dauer=dauer_text(a, b),
            )
        )

    def einfuegen_klick() -> None:
        a = start_zeit[0]
        b = ende_zeit[0]
        if a is None or b is None or b <= a:
            messagebox.showinfo(
                get_string("app.zeitaufzeichnung.dialog_kein_block_titel", locale),
                get_string("app.zeitaufzeichnung.dialog_kein_block_text", locale),
                parent=root,
            )
            return
        titel = titel_var.get().strip()
        if not titel:
            titel = get_string("app.zeitaufzeichnung.titel_standard", locale)
        einfuegen(a, b, titel)
        start_zeit[0] = None
        ende_zeit[0] = None
        b_einfuegen.configure(state=tk.DISABLED)
        status.configure(text=get_string("app.zeitaufzeichnung.status_eingefuegt", locale))

    btn_zeile = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    btn_zeile.pack(anchor=tk.W)

    b_start = tk.Button(
        btn_zeile,
        text=get_string("app.zeitaufzeichnung.btn_start", locale),
        command=start_klick,
        **btn_style(),
    )
    b_start.pack(side=tk.LEFT, padx=(0, 8))

    b_stop = tk.Button(
        btn_zeile,
        text=get_string("app.zeitaufzeichnung.btn_stop", locale),
        command=stop_klick,
        state=tk.DISABLED,
        **btn_style(),
    )
    b_stop.pack(side=tk.LEFT, padx=(0, 8))

    b_einfuegen = tk.Button(
        btn_zeile,
        text=get_string("app.zeitaufzeichnung.btn_einfuegen", locale),
        command=einfuegen_klick,
        state=tk.DISABLED,
        **btn_style(),
    )
    b_einfuegen.pack(side=tk.LEFT)

    tk.Label(
        aussen,
        text=get_string("app.zeitaufzeichnung.datei_hinweis", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 9),
        wraplength=560,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(16, 0))
