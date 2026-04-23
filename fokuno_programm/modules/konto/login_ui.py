"""Login-Oberfläche (Tk) für die App-Shell."""

from __future__ import annotations

from collections.abc import Callable

import tkinter as tk
from tkinter import messagebox

from locales import get_string
from modules.fenster_info import (
    startaufruf_zaehlen,
    startscreen_english_block,
    zeitstempel_jetzt,
)
from modules.konto.speicher import Benutzer, anmelden
from modules.theming.farben import kalender_farben
from modules.version_info import load_version_info


def login_ansicht_in(
    parent: tk.Misc,
    locale: str,
    on_erfolg: Callable[[Benutzer], None],
) -> Callable[[], None]:
    """Baut die Login-Maske in parent. Rückgabe: sensible Felder leeren (z. B. nach Abmeldung)."""

    kf = kalender_farben()
    root = parent.winfo_toplevel()
    version_info = load_version_info()
    start_counter = startaufruf_zaehlen(version_info.version)

    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True)

    inner = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    inner.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

    tk.Label(
        inner,
        text=get_string("app.konto.login_titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 18, "bold"),
    ).pack(anchor=tk.CENTER, pady=(0, 16))

    info_label = tk.Label(
        inner,
        text=startscreen_english_block(
            version_info,
            zeitstempel_jetzt(),
            start_counter,
            locale=locale,
        ),
        bg=kf.HINTERGRUND_FENSTER,
        fg="#6F6B64",
        font=("Segoe UI", 9),
        wraplength=560,
        justify=tk.LEFT,
    )

    user_var = tk.StringVar()
    pass_var = tk.StringVar()

    zeile_user = tk.Frame(inner, bg=kf.HINTERGRUND_FENSTER)
    zeile_user.pack(fill=tk.X, pady=(0, 8))
    tk.Label(
        zeile_user,
        text=get_string("app.konto.label_benutzer", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        width=12,
        anchor=tk.W,
    ).pack(side=tk.LEFT)
    user_e = tk.Entry(
        zeile_user,
        textvariable=user_var,
        width=28,
        font=("Segoe UI", 10),
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        insertbackground=kf.TEXT_ZEIT,
    )
    user_e.pack(side=tk.LEFT, fill=tk.X, expand=True)

    zeile_pw = tk.Frame(inner, bg=kf.HINTERGRUND_FENSTER)
    zeile_pw.pack(fill=tk.X, pady=(0, 6))
    tk.Label(
        zeile_pw,
        text=get_string("app.konto.label_passwort", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        width=12,
        anchor=tk.W,
    ).pack(side=tk.LEFT)
    pw_e = tk.Entry(
        zeile_pw,
        textvariable=pass_var,
        width=28,
        show="*",
        font=("Segoe UI", 10),
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        insertbackground=kf.TEXT_ZEIT,
    )
    pw_e.pack(side=tk.LEFT, fill=tk.X, expand=True)

    fehler = tk.Label(
        inner,
        text="",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.JETZT_ZEIGER,
        font=("Segoe UI", 9),
        wraplength=360,
        justify=tk.CENTER,
    )
    fehler.pack(anchor=tk.CENTER, pady=(4, 8))

    def passwort_vergessen_klick() -> None:
        messagebox.showinfo(
            get_string("app.konto.passwort_vergessen_titel", locale),
            get_string("app.konto.passwort_vergessen_text", locale),
            parent=root,
        )

    def registrieren_klick() -> None:
        messagebox.showinfo(
            get_string("app.konto.registrieren_titel", locale),
            get_string("app.konto.registrieren_text", locale),
            parent=root,
        )

    link_font = ("Segoe UI", 9, "underline")
    lf = tk.Frame(inner, bg=kf.HINTERGRUND_FENSTER)
    lf.pack(anchor=tk.CENTER, pady=(0, 4))
    b_pw = tk.Label(
        lf,
        text=get_string("app.konto.passwort_vergessen", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_UNTERKULMINATION,
        font=link_font,
        cursor="hand2",
    )
    b_pw.pack()
    b_pw.bind("<Button-1>", lambda _e: passwort_vergessen_klick())

    b_reg = tk.Label(
        inner,
        text=get_string("app.konto.registrieren_link", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_UNTERKULMINATION,
        font=link_font,
        cursor="hand2",
        wraplength=400,
        justify=tk.CENTER,
    )
    b_reg.pack(anchor=tk.CENTER, pady=(0, 16))
    b_reg.bind("<Button-1>", lambda _e: registrieren_klick())

    def anmelden_klick() -> None:
        fehler.configure(text="")
        b = anmelden(user_var.get(), pass_var.get())
        if b is None:
            fehler.configure(text=get_string("app.konto.fehler_anmeldung", locale))
            return
        pass_var.set("")
        on_erfolg(b)

    btn_zeile = tk.Frame(inner, bg=kf.HINTERGRUND_FENSTER)
    btn_zeile.pack(anchor=tk.CENTER)
    tk.Button(
        btn_zeile,
        text=get_string("app.konto.btn_anmelden", locale),
        command=anmelden_klick,
        font=("Segoe UI", 10),
        padx=16,
        pady=4,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        activeforeground=kf.TEXT_ZEIT,
        relief=tk.FLAT,
    ).pack()

    info_label.pack(anchor=tk.W, pady=(14, 0))

    user_e.focus_set()

    def sensibles_leeren() -> None:
        pass_var.set("")
        fehler.configure(text="")

    def enter_anmelden(_e: tk.Event | None = None) -> None:
        anmelden_klick()

    user_e.bind("<Return>", enter_anmelden)
    pw_e.bind("<Return>", enter_anmelden)

    return sensibles_leeren
