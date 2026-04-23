"""Toolbox-Modul Kontakte (ehemals Adressbuch, Schwerpunkt medizinische Versorgung)."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk
from zoneinfo import ZoneInfo

from locales import get_string
from modules.kalender.zeitaufzeichnung_speicher import kontakt_bearbeitung_spur_setzen
from modules.theming.farben import kalender_farben

from .kategorie_einstellungen import kategorie_einstellungen_oeffnen
from .kategorie_konfig import (
    braucht_fachrichtung,
    hat_stufe2,
    hat_stufe3,
    kategorien_laden,
    label_stufe1,
    label_stufe2,
    label_stufe3,
    ober_nach_id,
    stufe2_nach_id,
)
from .speicher import (
    STANDARD_FACHRICHTUNGEN,
    AnsprechpartnerEintrag,
    alle_aerzte,
    alle_favoriten,
    arzt_aktualisieren,
    arzt_hinzufuegen,
    arzt_loeschen,
    arzt_mit_id,
    export_aerzte_json,
    letzter_kontakt_genutzt_id_laden,
    letzter_kontakt_genutzt_id_speichern,
    letzter_kontakt_gespeichert_id_laden,
    letzter_kontakt_gespeichert_id_speichern,
)

_SYM_LUPE = "\U0001F50D"


def _zeitpunkt_text(zeitpunkt: dt.datetime) -> str:
    return zeitpunkt.strftime("%d.%m.%Y %H:%M")


def adressbuch_in(
    parent: tk.Misc,
    locale: str = "de",
    vorauswahl_id: str | None = None,
    on_aenderung: Callable[[], None] | None = None,
    on_zum_kalender: Callable[[dt.date], None] | None = None,
) -> None:
    """Baut die Kontakte-Ansicht in den uebergebenen Container."""
    kf = kalender_farben()
    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    tk.Label(
        aussen,
        text=get_string("app.kontakte.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
        anchor=tk.W,
    ).pack(fill=tk.X)

    listen_ids: list[str] = []
    bearbeitungs_id: list[str | None] = [None]
    sync = [False]
    fav_expanded: list[bool] = [False]

    such_var = tk.StringVar()

    titel_var = tk.StringVar()
    name_var = tk.StringVar()
    fach_var = tk.StringVar(value=STANDARD_FACHRICHTUNGEN[0])
    telefon_var = tk.StringVar()
    email_var = tk.StringVar()
    adresse_var = tk.StringVar()
    notiz_var = tk.StringVar()
    erstellt_var = tk.StringVar(value="-")
    geaendert_var = tk.StringVar(value="-")
    kategorie_haupt_var = tk.StringVar(value="")
    kategorie_unter_var = tk.StringVar(value="")
    kategorie_detail_var = tk.StringVar(value="")
    kundennummer_var = tk.StringVar()
    favorit_var = tk.BooleanVar(value=False)
    verknuepfung_var = tk.StringVar()
    ap_zeilen: list[dict[str, object]] = []

    def _schema_aktuell():
        return kategorien_laden()

    # —— Suche + Icon-Leiste (Favoriten, zuletzt genutzt, zuletzt gespeichert)
    kopf = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    kopf.pack(fill=tk.X, pady=(6, 4))

    such_zeile = tk.Frame(kopf, bg=kf.HINTERGRUND_FENSTER)
    such_zeile.pack(fill=tk.X)
    tk.Label(
        such_zeile,
        text=_SYM_LUPE,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 12),
        width=2,
    ).pack(side=tk.LEFT, padx=(0, 4))
    such_entry = tk.Entry(
        such_zeile,
        textvariable=such_var,
        font=("Segoe UI", 10),
    )
    such_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    icon_zeile = tk.Frame(kopf, bg=kf.HINTERGRUND_FENSTER)
    icon_zeile.pack(fill=tk.X, pady=(8, 0))

    def _icon_knopf(text: str, cmd: Callable[[], None]) -> tk.Button:
        b = tk.Button(
            icon_zeile,
            text=text,
            command=cmd,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            activebackground=kf.RASTER_STUNDE,
            font=("Segoe UI", 14),
            width=3,
        )
        b.pack(side=tk.LEFT, padx=(0, 6))
        return b

    fav_icon_btn = _icon_knopf("\u2605", lambda: None)
    _icon_knopf("\u27F3", lambda: _letzter_genutzt_laden())
    _icon_knopf("\u2712", lambda: _letzter_gespeichert_laden())

    fav_inner = tk.Frame(aussen, bg=kf.HINTERGRUND_BLATT, bd=0, highlightthickness=1, highlightbackground=kf.TRENNLINIE)
    fav_liste = tk.Listbox(
        fav_inner,
        height=4,
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        selectbackground=kf.HINTERGRUND_ZEITLEISTE,
        selectforeground=kf.TEXT_ZEIT,
        bd=0,
        highlightthickness=0,
        activestyle="none",
        font=("Segoe UI", 9),
    )
    fav_liste.pack(fill=tk.X, padx=4, pady=4)
    fav_listen_ids: list[str] = []

    form = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    form.pack(fill=tk.X, pady=(6, 0))

    def _feld(ueber: str, var: tk.StringVar) -> tk.Entry:
        zeile = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
        zeile.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            zeile,
            text=ueber,
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            anchor=tk.W,
        ).pack(fill=tk.X)
        eingabe = tk.Entry(zeile, textvariable=var)
        eingabe.pack(fill=tk.X, pady=(2, 0))
        return eingabe

    kat_kopf = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    kat_kopf.pack(fill=tk.X, pady=(0, 6))
    ober_zeile = tk.Frame(kat_kopf, bg=kf.HINTERGRUND_FENSTER)
    ober_zeile.pack(fill=tk.X)
    tk.Label(
        ober_zeile,
        text=get_string("app.kontakte.label_kat_stufe1", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
    ).pack(side=tk.LEFT, padx=(0, 8))
    combo_ober = ttk.Combobox(
        ober_zeile,
        state="readonly",
        width=32,
        font=("Segoe UI", 9),
    )
    combo_ober.pack(side=tk.LEFT, fill=tk.X, expand=True)
    tk.Button(
        ober_zeile,
        text=get_string("app.kontakte.btn_kat_einstellungen", locale),
        command=lambda: kategorie_einstellungen_oeffnen(
            aussen, locale, on_gespeichert=_nach_kat_einstellungen,
        ),
        font=("Segoe UI", 9),
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        padx=8,
        pady=2,
    ).pack(side=tk.RIGHT, padx=(8, 0))

    unter_zeile = tk.Frame(kat_kopf, bg=kf.HINTERGRUND_FENSTER)
    tk.Label(
        unter_zeile,
        text=get_string("app.kontakte.label_kat_stufe2", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
    ).pack(side=tk.LEFT, padx=(0, 8))
    combo_unter = ttk.Combobox(
        unter_zeile,
        state="readonly",
        width=36,
        font=("Segoe UI", 9),
    )
    combo_unter.pack(side=tk.LEFT, fill=tk.X, expand=True)

    stufe3_zeile = tk.Frame(kat_kopf, bg=kf.HINTERGRUND_FENSTER)
    tk.Label(
        stufe3_zeile,
        text=get_string("app.kontakte.label_kat_stufe3", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
    ).pack(side=tk.LEFT, padx=(0, 8))
    combo_stufe3 = ttk.Combobox(
        stufe3_zeile,
        state="readonly",
        width=36,
        font=("Segoe UI", 9),
    )
    combo_stufe3.pack(side=tk.LEFT, fill=tk.X, expand=True)

    ober_ids_ref: list[str] = []
    unter_ids_ref: list[str] = []
    stufe3_ids_ref: list[str] = []

    def _sync_ober_combo() -> None:
        schema = _schema_aktuell()
        labels = [o.label for o in schema.stufe1]
        ober_ids_ref.clear()
        ober_ids_ref.extend(o.id for o in schema.stufe1)
        combo_ober["values"] = tuple(labels)
        kh = kategorie_haupt_var.get().strip()
        if kh in ober_ids_ref:
            combo_ober.current(ober_ids_ref.index(kh))
        else:
            combo_ober.set("")

    def _sync_unter_combo() -> None:
        schema = _schema_aktuell()
        kh = kategorie_haupt_var.get().strip()
        o = ober_nach_id(schema, kh)
        unter_ids_ref.clear()
        if o is None or not hat_stufe2(o):
            combo_unter.set("")
            combo_unter["values"] = ()
            return
        labs = [u.label for u in o.stufe2]
        unter_ids_ref.extend(u.id for u in o.stufe2)
        combo_unter["values"] = tuple(labs)
        ku = kategorie_unter_var.get().strip()
        if ku in unter_ids_ref:
            combo_unter.current(unter_ids_ref.index(ku))
        elif o.stufe2:
            combo_unter.current(0)
            kategorie_unter_var.set(unter_ids_ref[0])
        else:
            combo_unter.set("")

    def _sync_stufe3_combo() -> None:
        schema = _schema_aktuell()
        kh = kategorie_haupt_var.get().strip()
        ku = kategorie_unter_var.get().strip()
        o = ober_nach_id(schema, kh)
        stufe3_ids_ref.clear()
        if o is None:
            combo_stufe3.set("")
            combo_stufe3["values"] = ()
            return
        u = stufe2_nach_id(o, ku)
        if u is None or not hat_stufe3(u):
            combo_stufe3.set("")
            combo_stufe3["values"] = ()
            return
        labs = [z.label for z in u.stufe3]
        stufe3_ids_ref.extend(z.id for z in u.stufe3)
        combo_stufe3["values"] = tuple(labs)
        kd = kategorie_detail_var.get().strip()
        if kd in stufe3_ids_ref:
            combo_stufe3.current(stufe3_ids_ref.index(kd))
        elif u.stufe3:
            combo_stufe3.current(0)
            kategorie_detail_var.set(stufe3_ids_ref[0])
        else:
            combo_stufe3.set("")

    def _unter_stufe3_layout() -> None:
        schema = _schema_aktuell()
        kh = kategorie_haupt_var.get().strip()
        o = ober_nach_id(schema, kh)
        if o is None or not hat_stufe2(o):
            unter_zeile.pack_forget()
            stufe3_zeile.pack_forget()
            kategorie_unter_var.set("")
            kategorie_detail_var.set("")
            return
        unter_zeile.pack(fill=tk.X, pady=(4, 0))
        ku = kategorie_unter_var.get().strip()
        u = stufe2_nach_id(o, ku)
        if u is not None and hat_stufe3(u):
            stufe3_zeile.pack(fill=tk.X, pady=(4, 0))
        else:
            stufe3_zeile.pack_forget()
            kategorie_detail_var.set("")

    def _sync_kategorie_combos() -> None:
        _sync_ober_combo()
        _sync_unter_combo()
        _unter_stufe3_layout()
        _sync_stufe3_combo()

    def _on_ober_gewaehlt(_e: tk.Event | None = None) -> None:
        i = combo_ober.current()
        if i < 0 or i >= len(ober_ids_ref):
            return
        sync[0] = True
        kategorie_haupt_var.set(ober_ids_ref[i])
        kategorie_unter_var.set("")
        kategorie_detail_var.set("")
        sync[0] = False
        _sync_unter_combo()
        _unter_stufe3_layout()
        _sync_stufe3_combo()
        _medizin_form_sichtbarkeit()
        _fach_sichtbarkeit()

    def _on_unter_gewaehlt(_e: tk.Event | None = None) -> None:
        i = combo_unter.current()
        if i < 0 or i >= len(unter_ids_ref):
            return
        sync[0] = True
        kategorie_unter_var.set(unter_ids_ref[i])
        kategorie_detail_var.set("")
        sync[0] = False
        _unter_stufe3_layout()
        _sync_stufe3_combo()
        _medizin_form_sichtbarkeit()
        _fach_sichtbarkeit()

    def _on_stufe3_gewaehlt(_e: tk.Event | None = None) -> None:
        i = combo_stufe3.current()
        if i < 0 or i >= len(stufe3_ids_ref):
            return
        sync[0] = True
        kategorie_detail_var.set(stufe3_ids_ref[i])
        sync[0] = False
        _fach_sichtbarkeit()

    def _nach_kat_einstellungen() -> None:
        _sync_kategorie_combos()
        _liste_refresh()

    combo_ober.bind("<<ComboboxSelected>>", _on_ober_gewaehlt)
    combo_unter.bind("<<ComboboxSelected>>", _on_unter_gewaehlt)
    combo_stufe3.bind("<<ComboboxSelected>>", _on_stufe3_gewaehlt)

    medizin_block = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    tk.Label(
        medizin_block,
        text=get_string("app.kontakte.abschnitt_medizin_detail", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
    ).pack(fill=tk.X, pady=(0, 4))

    fach_zeile = tk.Frame(medizin_block, bg=kf.HINTERGRUND_FENSTER)
    fach_zeile.pack(fill=tk.X, pady=(0, 6))
    fach_label = tk.Label(
        fach_zeile,
        text=get_string("app.kontakte.feld_fachrichtung", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
    )
    fach_combo = ttk.Combobox(
        fach_zeile,
        textvariable=fach_var,
        values=STANDARD_FACHRICHTUNGEN,
        state="readonly",
        width=28,
        font=("Segoe UI", 9),
    )

    def _fach_sichtbarkeit() -> None:
        if sync[0]:
            return
        if braucht_fachrichtung(
            kategorie_haupt_var.get().strip(),
            kategorie_unter_var.get().strip(),
        ):
            fach_label.pack(fill=tk.X)
            fach_combo.pack(fill=tk.X, pady=(2, 0))
        else:
            fach_label.pack_forget()
            fach_combo.pack_forget()

    def _medizin_form_sichtbarkeit() -> None:
        if sync[0]:
            return
        if kategorie_haupt_var.get() == "medizin":
            medizin_block.pack(fill=tk.X, pady=(0, 6))
            _fach_sichtbarkeit()
        else:
            medizin_block.pack_forget()
            fach_label.pack_forget()
            fach_combo.pack_forget()

    _sync_kategorie_combos()
    _medizin_form_sichtbarkeit()

    _feld(get_string("app.kontakte.feld_titel", locale), titel_var)
    _feld(get_string("app.kontakte.feld_name", locale), name_var)
    _feld(get_string("app.kontakte.feld_kundennummer", locale), kundennummer_var)

    _feld(get_string("app.kontakte.feld_telefon", locale), telefon_var)
    _feld(get_string("app.kontakte.feld_email", locale), email_var)
    _feld(get_string("app.kontakte.feld_adresse", locale), adresse_var)

    tk.Label(
        form,
        text=get_string("app.kontakte.abschnitt_ansprechpartner", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 9, "bold"),
        anchor=tk.W,
    ).pack(fill=tk.X, pady=(0, 4))
    ap_box = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    ap_box.pack(fill=tk.X, pady=(0, 6))

    def _ap_sammeln() -> tuple[AnsprechpartnerEintrag, ...]:
        out: list[AnsprechpartnerEintrag] = []
        for z in ap_zeilen:
            rv = z["rolle"]
            nv = z["name"]
            tv = z["telefon"]
            ev = z["email"]
            zv = z["notiz"]
            assert isinstance(rv, tk.StringVar)
            assert isinstance(nv, tk.StringVar)
            assert isinstance(tv, tk.StringVar)
            assert isinstance(ev, tk.StringVar)
            assert isinstance(zv, tk.StringVar)
            rolle = rv.get().strip()
            name = nv.get().strip()
            tel = tv.get().strip()
            em = ev.get().strip()
            no = zv.get().strip()
            if not any((rolle, name, tel, em, no)):
                continue
            out.append(AnsprechpartnerEintrag(rolle, name, tel, em, no))
        return tuple(out)

    def _ap_entfernen(zeile: tk.Frame) -> None:
        zeile.destroy()
        ap_zeilen[:] = [x for x in ap_zeilen if x["frame"] is not zeile]  # type: ignore[misc]

    def _ap_zeile_bauen(ap: AnsprechpartnerEintrag | None = None) -> None:
        p = ap or AnsprechpartnerEintrag("", "", "", "", "")
        row = tk.Frame(ap_box, bg=kf.HINTERGRUND_FENSTER)
        row.pack(fill=tk.X, pady=(0, 6))
        r1 = tk.Frame(row, bg=kf.HINTERGRUND_FENSTER)
        r1.pack(fill=tk.X)
        vr = tk.StringVar(value=p.rolle)
        vn = tk.StringVar(value=p.name)
        tk.Label(
            r1,
            text=get_string("app.kontakte.ap_rolle", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8),
            width=10,
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Entry(r1, textvariable=vr, font=("Segoe UI", 9), width=12).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(
            r1,
            text=get_string("app.kontakte.ap_name", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8),
            width=8,
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Entry(r1, textvariable=vn, font=("Segoe UI", 9), width=16).pack(side=tk.LEFT, padx=(4, 4))
        tk.Button(
            r1,
            text="\u2715",
            width=2,
            command=lambda r=row: _ap_entfernen(r),
            font=("Segoe UI", 8),
            relief=tk.FLAT,
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            cursor="hand2",
        ).pack(side=tk.RIGHT)
        r2 = tk.Frame(row, bg=kf.HINTERGRUND_FENSTER)
        r2.pack(fill=tk.X, pady=(2, 0))
        vt = tk.StringVar(value=p.telefon)
        ve = tk.StringVar(value=p.email)
        vz = tk.StringVar(value=p.notiz)
        tk.Label(
            r2,
            text=get_string("app.kontakte.ap_telefon", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8),
            width=10,
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Entry(r2, textvariable=vt, font=("Segoe UI", 9), width=14).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(
            r2,
            text=get_string("app.kontakte.ap_email", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8),
            width=8,
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Entry(r2, textvariable=ve, font=("Segoe UI", 9), width=18).pack(side=tk.LEFT, padx=(4, 8))
        tk.Label(
            r2,
            text=get_string("app.kontakte.ap_notiz", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8),
            width=6,
            anchor=tk.W,
        ).pack(side=tk.LEFT)
        tk.Entry(r2, textvariable=vz, font=("Segoe UI", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        ap_zeilen.append(
            {
                "frame": row,
                "rolle": vr,
                "name": vn,
                "telefon": vt,
                "email": ve,
                "notiz": vz,
            }
        )

    def _ap_leeren() -> None:
        for w in ap_box.winfo_children():
            w.destroy()
        ap_zeilen.clear()

    def _ap_add_klick() -> None:
        _ap_zeile_bauen()

    tk.Button(
        form,
        text=get_string("app.kontakte.btn_ap_hinzufuegen", locale),
        command=_ap_add_klick,
        font=("Segoe UI", 9),
        relief=tk.FLAT,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        cursor="hand2",
    ).pack(anchor=tk.W, pady=(0, 6))

    _ap_zeile_bauen()

    _feld(get_string("app.kontakte.feld_notiz", locale), notiz_var)

    _feld(get_string("app.kontakte.feld_verknuepfung", locale), verknuepfung_var)

    fav_cb = tk.Checkbutton(
        form,
        text=get_string("app.kontakte.feld_favorit", locale),
        variable=favorit_var,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.HINTERGRUND_FENSTER,
        selectcolor=kf.HINTERGRUND_BLATT,
        font=("Segoe UI", 10),
        anchor=tk.W,
    )
    fav_cb.pack(fill=tk.X, pady=(0, 6))

    meta = tk.Frame(aussen, bg=kf.HINTERGRUND_ZEITLEISTE)
    meta.pack(fill=tk.X, pady=(6, 8))
    tk.Label(
        meta,
        textvariable=erstellt_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        padx=10,
        pady=2,
    ).pack(fill=tk.X)
    tk.Label(
        meta,
        textvariable=geaendert_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        padx=10,
        pady=2,
    ).pack(fill=tk.X, pady=(0, 4))

    kalender_btn_zeile = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)

    def _zum_kalender_klick() -> None:
        if on_zum_kalender is None:
            return
        bid = bearbeitungs_id[0]
        if not bid:
            return
        kontakt = arzt_mit_id(bid)
        if kontakt is None:
            return
        on_zum_kalender(kontakt.geaendert_am.date())

    kalender_jump_btn = tk.Button(
        kalender_btn_zeile,
        text=get_string("app.kontakte.btn_zum_kalender", locale),
        command=_zum_kalender_klick,
        font=("Segoe UI", 9),
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        pady=4,
    )
    kalender_jump_btn.pack(anchor=tk.W)

    def _sync_kalender_button() -> None:
        if on_zum_kalender is None:
            kalender_btn_zeile.pack_forget()
            return
        kalender_btn_zeile.pack(fill=tk.X, pady=(0, 6))
        if bearbeitungs_id[0]:
            kalender_jump_btn.configure(state=tk.NORMAL)
        else:
            kalender_jump_btn.configure(state=tk.DISABLED)

    liste = tk.Listbox(
        aussen,
        height=7,
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        selectbackground=kf.HINTERGRUND_ZEITLEISTE,
        selectforeground=kf.TEXT_ZEIT,
        bd=0,
        highlightthickness=0,
        activestyle="none",
    )

    def _kontakt_zeile(k) -> str:
        fav = "\u2605 " if k.favorit else ""
        schema = _schema_aktuell()
        h = label_stufe1(schema, k.kategorie_haupt)
        parts: list[str] = [h]
        o = ober_nach_id(schema, k.kategorie_haupt)
        if o is not None and (k.kategorie_unter or "").strip():
            parts.append(label_stufe2(schema, k.kategorie_haupt, k.kategorie_unter))
            u = stufe2_nach_id(o, k.kategorie_unter)
            if u is not None and (k.kategorie_detail or "").strip() and hat_stufe3(u):
                parts.append(
                    label_stufe3(
                        schema,
                        k.kategorie_haupt,
                        k.kategorie_unter,
                        k.kategorie_detail,
                    )
                )
        kern_basis = " · ".join(parts)
        if braucht_fachrichtung(k.kategorie_haupt, k.kategorie_unter):
            kern = (
                f"{kern_basis} · {k.fachrichtung or '-'} | "
                f"{k.anzeige_name()} | {k.telefon or '-'}"
            )
        else:
            kern = f"{kern_basis} | {k.anzeige_name()} | {k.telefon or '-'}"
        return f"{fav}{kern}"

    def _passiert_filter(k, q: str) -> bool:
        if not q:
            return True
        schema = _schema_aktuell()
        teile = [
            k.name,
            k.titel,
            k.fachrichtung,
            k.telefon,
            k.email,
            k.adresse,
            k.notiz,
            k.kundennummer,
            label_stufe1(schema, k.kategorie_haupt),
        ]
        if (k.kategorie_unter or "").strip():
            teile.append(label_stufe2(schema, k.kategorie_haupt, k.kategorie_unter))
        if (k.kategorie_detail or "").strip():
            teile.append(
                label_stufe3(
                    schema,
                    k.kategorie_haupt,
                    k.kategorie_unter,
                    k.kategorie_detail,
                )
            )
        for ap in k.ansprechpartner:
            teile.extend([ap.rolle, ap.name, ap.telefon, ap.email, ap.notiz])
        blob = " ".join(teile).lower()
        return q in blob

    def _liste_refresh() -> None:
        liste.delete(0, tk.END)
        listen_ids.clear()
        q = such_var.get().strip().lower()
        for arzt in alle_aerzte():
            if not _passiert_filter(arzt, q):
                continue
            liste.insert(tk.END, _kontakt_zeile(arzt))
            listen_ids.append(arzt.id)

    def _fav_liste_refresh() -> None:
        fav_liste.delete(0, tk.END)
        fav_listen_ids.clear()
        for arzt in alle_favoriten():
            fav_liste.insert(tk.END, _kontakt_zeile(arzt))
            fav_listen_ids.append(arzt.id)

    def _fav_toggle() -> None:
        fav_expanded[0] = not fav_expanded[0]
        if fav_expanded[0]:
            fav_inner.pack(fill=tk.X, pady=(4, 0))
            _fav_liste_refresh()
        else:
            fav_inner.pack_forget()

    fav_icon_btn.configure(command=_fav_toggle)

    def _fav_auswahl(_e: tk.Event | None = None) -> None:
        if not fav_expanded[0]:
            return
        aus = fav_liste.curselection()
        if not aus:
            return
        i = int(aus[0])
        if 0 <= i < len(fav_listen_ids):
            kid = fav_listen_ids[i]
            _laden(kid)
            liste.selection_clear(0, tk.END)
            try:
                j = listen_ids.index(kid)
                liste.selection_set(j)
                liste.see(j)
            except ValueError:
                pass
            _fav_toggle()

    fav_liste.bind("<<ListboxSelect>>", _fav_auswahl)
    fav_liste.bind("<Double-Button-1>", _fav_auswahl)

    def _formular_leeren() -> None:
        sync[0] = True
        bearbeitungs_id[0] = None
        titel_var.set("")
        name_var.set("")
        fach_var.set(STANDARD_FACHRICHTUNGEN[0])
        telefon_var.set("")
        email_var.set("")
        adresse_var.set("")
        notiz_var.set("")
        kundennummer_var.set("")
        erstellt_var.set(get_string("app.kontakte.meta_erstellt_leer", locale))
        geaendert_var.set(get_string("app.kontakte.meta_geaendert_leer", locale))
        kategorie_haupt_var.set("")
        kategorie_unter_var.set("")
        kategorie_detail_var.set("")
        favorit_var.set(False)
        verknuepfung_var.set("")
        sync[0] = False
        _sync_kategorie_combos()
        _medizin_form_sichtbarkeit()
        _fach_sichtbarkeit()
        _ap_leeren()
        _ap_zeile_bauen()
        _sync_kalender_button()
        liste.selection_clear(0, tk.END)

    def _laden(arzt_id: str) -> None:
        arzt = arzt_mit_id(arzt_id)
        if arzt is None:
            return
        sync[0] = True
        bearbeitungs_id[0] = arzt.id
        titel_var.set(arzt.titel)
        name_var.set(arzt.name)
        fach_var.set(arzt.fachrichtung or STANDARD_FACHRICHTUNGEN[0])
        telefon_var.set(arzt.telefon)
        email_var.set(arzt.email)
        adresse_var.set(arzt.adresse)
        notiz_var.set(arzt.notiz)
        erstellt_var.set(
            get_string("app.kontakte.meta_erstellt", locale).format(
                zeit=_zeitpunkt_text(arzt.erstellt_am)
            )
        )
        geaendert_var.set(
            get_string("app.kontakte.meta_geaendert", locale).format(
                zeit=_zeitpunkt_text(arzt.geaendert_am)
            )
        )
        kategorie_haupt_var.set(arzt.kategorie_haupt)
        kategorie_unter_var.set(arzt.kategorie_unter)
        kategorie_detail_var.set(arzt.kategorie_detail)
        kundennummer_var.set(arzt.kundennummer)
        favorit_var.set(arzt.favorit)
        verknuepfung_var.set(arzt.verknuepfung_id)
        sync[0] = False
        _sync_kategorie_combos()
        _medizin_form_sichtbarkeit()
        _fach_sichtbarkeit()
        _ap_leeren()
        if arzt.ansprechpartner:
            for ap in arzt.ansprechpartner:
                _ap_zeile_bauen(ap)
        else:
            _ap_zeile_bauen()
        _sync_kalender_button()
        letzter_kontakt_genutzt_id_speichern(arzt_id)

    def _letzter_in_liste_markieren(lid: str) -> None:
        try:
            j = listen_ids.index(lid)
            liste.selection_clear(0, tk.END)
            liste.selection_set(j)
            liste.see(j)
        except ValueError:
            such_var.set("")
            _liste_refresh()
            try:
                j = listen_ids.index(lid)
                liste.selection_set(j)
                liste.see(j)
            except ValueError:
                pass

    def _letzter_genutzt_laden() -> None:
        lid = letzter_kontakt_genutzt_id_laden()
        if not lid or arzt_mit_id(lid) is None:
            messagebox.showinfo(
                get_string("app.kontakte.hinweis_titel", locale),
                get_string("app.kontakte.letzter_genutzt_keiner", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        _laden(lid)
        _letzter_in_liste_markieren(lid)

    def _letzter_gespeichert_laden() -> None:
        lid = letzter_kontakt_gespeichert_id_laden()
        if not lid or arzt_mit_id(lid) is None:
            messagebox.showinfo(
                get_string("app.kontakte.hinweis_titel", locale),
                get_string("app.kontakte.letzter_gespeichert_keiner", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        _laden(lid)
        _letzter_in_liste_markieren(lid)

    def _speichern() -> None:
        if not name_var.get().strip():
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                get_string("app.kontakte.fehler_name_leer", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        kh = kategorie_haupt_var.get().strip()
        if not kh:
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                get_string("app.kontakte.fehler_pfad_leer", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        schema_sp = _schema_aktuell()
        o_sp = ober_nach_id(schema_sp, kh)
        if o_sp is not None and hat_stufe2(o_sp) and not kategorie_unter_var.get().strip():
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                get_string("app.kontakte.fehler_kategorie_leer", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        u_sp = (
            stufe2_nach_id(o_sp, kategorie_unter_var.get())
            if o_sp is not None and hat_stufe2(o_sp)
            else None
        )
        if (
            u_sp is not None
            and hat_stufe3(u_sp)
            and not kategorie_detail_var.get().strip()
        ):
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                get_string("app.kontakte.fehler_stufe3_leer", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        ku_med = kategorie_unter_var.get().strip()
        kd_hw = kategorie_detail_var.get().strip()
        kw = dict(
            titel=titel_var.get(),
            name=name_var.get(),
            fachrichtung=fach_var.get()
            if braucht_fachrichtung(kh, kategorie_unter_var.get().strip())
            else "",
            telefon=telefon_var.get(),
            email=email_var.get(),
            adresse=adresse_var.get(),
            notiz=notiz_var.get(),
            favorit=favorit_var.get(),
            kategorie_haupt=kh,
            kategorie_unter=ku_med,
            kategorie_detail=kd_hw,
            verknuepfung_id=verknuepfung_var.get(),
            kundennummer=kundennummer_var.get(),
            ansprechpartner=_ap_sammeln(),
        )
        if bearbeitungs_id[0]:
            kontakt = arzt_aktualisieren(bearbeitungs_id[0], **kw)
            if kontakt is None:
                return
        else:
            kontakt = arzt_hinzufuegen(**kw)
        ziel = kontakt.id
        try:
            kontakt_bearbeitung_spur_setzen(
                kontakt.id,
                get_string("app.kontakte.kalender_spur_titel", locale).format(
                    name=kontakt.anzeige_name()
                ),
                kontakt.geaendert_am,
                ZoneInfo("Europe/Berlin"),
            )
        except OSError:
            pass
        letzter_kontakt_gespeichert_id_speichern(ziel)
        letzter_kontakt_genutzt_id_speichern(ziel)
        _liste_refresh()
        _fav_liste_refresh()
        _laden(ziel)
        try:
            j = listen_ids.index(ziel)
            liste.selection_set(j)
            liste.see(j)
        except ValueError:
            pass
        if on_aenderung is not None:
            on_aenderung()

    def _loeschen() -> None:
        arzt_id = bearbeitungs_id[0]
        if not arzt_id:
            return
        if not messagebox.askyesno(
            get_string("app.kontakte.loeschen_titel", locale),
            get_string("app.kontakte.loeschen_frage", locale),
            parent=parent.winfo_toplevel(),
        ):
            return
        if arzt_loeschen(arzt_id):
            _formular_leeren()
            _liste_refresh()
            _fav_liste_refresh()
            if on_aenderung is not None:
                on_aenderung()

    def _export() -> None:
        ziel = filedialog.asksaveasfilename(
            parent=parent.winfo_toplevel(),
            title=get_string("app.kontakte.export_titel", locale),
            defaultextension=".json",
            initialfile="kontakte_export.json",
            filetypes=[("JSON", "*.json"), ("Alle Dateien", "*.*")],
        )
        if not ziel:
            return
        try:
            pfad = export_aerzte_json(ziel)
        except OSError as exc:
            messagebox.showerror(
                get_string("app.kontakte.fehler_titel", locale),
                str(exc),
                parent=parent.winfo_toplevel(),
            )
            return
        messagebox.showinfo(
            get_string("app.kontakte.export_titel", locale),
            get_string("app.kontakte.export_erfolg", locale).format(pfad=pfad),
            parent=parent.winfo_toplevel(),
        )

    def _liste_auswahl(_event: tk.Event | None = None) -> None:
        if sync[0]:
            return
        auswahl = liste.curselection()
        if not auswahl:
            return
        index = int(auswahl[0])
        if 0 <= index < len(listen_ids):
            _laden(listen_ids[index])

    def _such_oder_filter_aenderung(*_a: object) -> None:
        if sync[0]:
            return
        _liste_refresh()

    such_var.trace_add("write", lambda *_: _such_oder_filter_aenderung())
    kategorie_haupt_var.trace_add("write", lambda *_: _medizin_form_sichtbarkeit())
    kategorie_unter_var.trace_add("write", lambda *_: _fach_sichtbarkeit())

    btns = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    btns.pack(fill=tk.X, pady=(0, 6))
    for c in range(2):
        btns.grid_columnconfigure(c, weight=1, uniform="kbtn")

    tk.Button(
        btns,
        text=get_string("app.kontakte.btn_neu", locale),
        command=_formular_leeren,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg="#2E7D32",
        fg="#FFFFFF",
        activebackground="#1B5E20",
        activeforeground="#FFFFFF",
        padx=8,
        pady=6,
    ).grid(row=0, column=0, sticky=tk.EW, padx=(0, 3), pady=(0, 3))
    tk.Button(
        btns,
        text=get_string("app.kontakte.btn_loeschen", locale),
        command=_loeschen,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg="#C62828",
        fg="#FFFFFF",
        activebackground="#8E0000",
        activeforeground="#FFFFFF",
        padx=8,
        pady=6,
    ).grid(row=0, column=1, sticky=tk.EW, padx=(3, 0), pady=(0, 3))
    tk.Button(
        btns,
        text=get_string("app.kontakte.btn_speichern", locale),
        command=_speichern,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg="#1565C0",
        fg="#FFFFFF",
        activebackground="#0D47A1",
        activeforeground="#FFFFFF",
        padx=8,
        pady=6,
    ).grid(row=1, column=0, sticky=tk.EW, padx=(0, 3), pady=(3, 0))
    tk.Button(
        btns,
        text=get_string("app.kontakte.btn_export", locale),
        command=_export,
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        bg="#6A1B9A",
        fg="#FFFFFF",
        activebackground="#4A148C",
        activeforeground="#FFFFFF",
        padx=8,
        pady=6,
    ).grid(row=1, column=1, sticky=tk.EW, padx=(3, 0), pady=(3, 0))

    liste.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

    liste.bind("<<ListboxSelect>>", _liste_auswahl)
    liste.bind("<Double-Button-1>", _liste_auswahl)

    _liste_refresh()
    _formular_leeren()
    if vorauswahl_id and vorauswahl_id in [k.id for k in alle_aerzte()]:
        _laden(vorauswahl_id)
        try:
            j = listen_ids.index(vorauswahl_id)
            liste.selection_set(j)
            liste.see(j)
        except ValueError:
            pass
    else:
        liste.selection_clear(0, tk.END)
