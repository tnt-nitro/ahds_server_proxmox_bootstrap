"""Modul fuer Krankmeldungen und Wiedervorstellung beim Arzt."""

from __future__ import annotations

import datetime as dt
import shutil
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from locales import get_string
from modules.adressbuch.speicher import (
    STANDARD_FACHRICHTUNGEN,
    alle_aerzte,
    arzt_hinzufuegen,
    arzt_mit_id,
)
from modules.arbeitszeit.einstellungen_speicher import laden as arbeitseinstellungen_laden
from modules.arbeitszeit.regelprofil import standard_regelarbeit
from modules.kalender_toolbox import mini_monat_in
from modules.krankmeldung.speicher import (
    alle_eintraege,
    eintrag_aktualisieren,
    eintrag_fuer_tag,
    eintrag_hinzufuegen,
    eintrag_loeschen,
    eintrag_mit_id,
)
from modules.pausenzeit.profil import standard_arbeitspausen
from modules.theming.farben import kalender_farben

_SYM_KALENDER = "\u25A3"

try:
    import cv2

    _KAMERA_OK = True
except ImportError:
    _KAMERA_OK = False


def _datum_als_text(tag: dt.date) -> str:
    return tag.strftime("%d.%m.%Y")


def _datum_parsen(text: str) -> dt.date:
    roh = text.strip()
    return dt.datetime.strptime(roh, "%d.%m.%Y").date()


def _zeitpunkt_als_text(zeitpunkt: dt.datetime) -> str:
    return zeitpunkt.strftime("%d.%m.%Y %H:%M")


def _zeit_parsen(text: str) -> tuple[int, int]:
    roh = text.strip()
    zeit = dt.datetime.strptime(roh, "%H:%M").time()
    return (zeit.hour, zeit.minute)


def _dokument_ordner() -> Path:
    ziel = Path.home() / "AhDs" / "Krankmeldung" / "Dokumente"
    ziel.mkdir(parents=True, exist_ok=True)
    return ziel


def _dokument_kopieren(quellpfad: str) -> str:
    quelle = Path(quellpfad)
    if not quelle.is_file():
        raise FileNotFoundError(quellpfad)
    zeit = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = quelle.suffix or ".bin"
    ziel = _dokument_ordner() / f"krankmeldung_{zeit}{suffix}"
    shutil.copy2(quelle, ziel)
    return str(ziel)


def _foto_aufnehmen_und_speichern() -> str:
    if not _KAMERA_OK:
        raise RuntimeError("kamera_nicht_verfuegbar")
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("kamera_nicht_verfuegbar")
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("kamera_bild_fehlt")
    zeit = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ziel = _dokument_ordner() / f"krankmeldung_foto_{zeit}.png"
    if not cv2.imwrite(str(ziel), frame):
        raise OSError("foto_speichern_fehlgeschlagen")
    return str(ziel)


def krankmeldung_in(
    parent: tk.Misc,
    locale: str = "de",
    vorauswahl_id: str | None = None,
    on_aenderung: Callable[[], None] | None = None,
) -> None:
    """Baut die Krankmeldungs-Ansicht in den uebergebenen Container."""
    kf = kalender_farben()

    # Kein zweites Canvas hier: die Toolbox (app_shell) scrollt bereits in einem Canvas
    # ein eingebettetes Frame. Verschachtelte Canvas-Fenster liefern oft falsche Hoehen,
    # sodass der Inhalt unter dem Mini-Kalender unsichtbar bleibt.
    wrap = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    aussen = tk.Frame(wrap, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True)

    titel_label = tk.Label(
        aussen,
        text=get_string("app.krankmeldung.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    )
    titel_label.pack(fill=tk.X)

    start_var = tk.StringVar()
    ende_var = tk.StringVar()
    arzt_var = tk.StringVar()
    arztzeit_var = tk.StringVar(value="09:00")
    termin_art_var = tk.StringVar(value="wiedervorstellung")
    arzt_auswahl_var = tk.StringVar(value="")
    arzt_id_var = tk.StringVar(value="")
    notiz_var = tk.StringVar()
    status_hinweis_var = tk.StringVar(value="")
    status_ende_var = tk.StringVar(value="")
    status_arzt_var = tk.StringVar(value="")
    krankheitstage_var = tk.StringVar(value="0")
    tage_gesamt_var = tk.StringVar(value="0")
    dokument_var = tk.StringVar(value="")
    dokument_status_var = tk.StringVar(value="")
    bearbeitungs_id: list[str | None] = [None]
    listen_ids: list[str] = []
    formular_sync_aktiv = [False]
    meta_modus_var = tk.StringVar(value="Neue Krankmeldung")
    meta_erstellt_var = tk.StringVar(value="-")
    meta_geaendert_var = tk.StringVar(value="-")
    meta_anzahl_var = tk.StringVar(value="0")
    arzt_optionen: list[tuple[str, str]] = []
    a_setzen_modus = [False]
    auswahl_start: list[dt.date | None] = [None]
    auswahl_ende: list[dt.date | None] = [None]

    kalender_kopf = tk.Label(
        aussen,
        text=f"{_SYM_KALENDER} {get_string('app.krankmeldung.kalender_titel', locale)}",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    )
    kalender_kopf.pack(fill=tk.X, pady=(0, 4))

    markierungs_farben = {
        "rahmen": "#E8B200",
        "bereich": "#FFD966",
    }

    def _arzt_label(arzt_id: str) -> str:
        arzt = arzt_mit_id(arzt_id)
        if arzt is None:
            return ""
        fach = arzt.fachrichtung or "-"
        return f"{fach}: {arzt.anzeige_name()}"

    def _arzt_optionen_aktualisieren(vorauswahl_id: str | None = None) -> None:
        del arzt_optionen[:]
        menu = arzt_menu["menu"]
        menu.delete(0, "end")
        for arzt in alle_aerzte():
            label = f"{arzt.fachrichtung or '-'}: {arzt.anzeige_name()}"
            arzt_optionen.append((label, arzt.id))
            menu.add_command(
                label=label,
                command=lambda lbl=label, aid=arzt.id: (
                    arzt_auswahl_var.set(lbl),
                    arzt_id_var.set(aid),
                ),
            )
        if not arzt_optionen:
            arzt_auswahl_var.set("Kein Arzt angelegt")
            arzt_id_var.set("")
            return
        if vorauswahl_id:
            for label, aid in arzt_optionen:
                if aid == vorauswahl_id:
                    arzt_auswahl_var.set(label)
                    arzt_id_var.set(aid)
                    return
        if arzt_id_var.get().strip():
            for label, aid in arzt_optionen:
                if aid == arzt_id_var.get().strip():
                    arzt_auswahl_var.set(label)
                    return
        arzt_auswahl_var.set(arzt_optionen[0][0])
        arzt_id_var.set(arzt_optionen[0][1])

    def _arzt_anlegen_dialog() -> None:
        name = simpledialog.askstring(
            "Arzt anlegen",
            "Name des Arztes:",
            parent=parent.winfo_toplevel(),
        )
        if not name or not name.strip():
            return
        fach = simpledialog.askstring(
            "Arzt anlegen",
            "Fachrichtung (z. B. Hausarzt, HNO):",
            initialvalue=STANDARD_FACHRICHTUNGEN[0],
            parent=parent.winfo_toplevel(),
        )
        kontakt = arzt_hinzufuegen(name=name.strip(), fachrichtung=(fach or "").strip() or STANDARD_FACHRICHTUNGEN[0])
        _arzt_optionen_aktualisieren(kontakt.id)

    def _tag_stil_fuer_kalender(tag: dt.date) -> dict[str, object] | None:
        start = auswahl_start[0]
        ende = auswahl_ende[0]
        arzt_tag: dt.date | None = None
        arzt_text = arzt_var.get().strip()
        if arzt_text:
            try:
                arzt_tag = _datum_parsen(arzt_text)
            except ValueError:
                arzt_tag = None
        stil: dict[str, object] = {}
        if start is not None and ende is not None:
            lo = min(start, ende)
            hi = max(start, ende)
            if lo <= tag <= hi:
                stil["bereich_markierung"] = True
                stil["bereich_farbe"] = markierungs_farben["bereich"]
        if arzt_tag is not None and tag == arzt_tag:
            stil["marker_text"] = "A"
            stil["marker_farbe"] = "#245B9E"
            stil["marker_text_farbe"] = "#FFFFFF"
        if (start is not None and tag == start) or (ende is not None and tag == ende):
            stil["rahmen_dicke"] = 2
            stil["rahmen_farbe"] = markierungs_farben["rahmen"]
        if stil:
            return stil
        return None

    def _setze_zeitraum(start: dt.date | None, ende: dt.date | None) -> None:
        auswahl_start[0] = start
        auswahl_ende[0] = ende
        start_var.set(_datum_als_text(start) if start is not None else "")
        ende_var.set(_datum_als_text(ende) if ende is not None else "")
        if ende is not None and not arzt_var.get().strip():
            arzt_var.set(_datum_als_text(ende))

    def _kalender_tag_geklickt(tag: dt.date) -> None:
        if a_setzen_modus[0]:
            arzt_var.set(_datum_als_text(tag))
            a_setzen_modus[0] = False
            a_setzen_btn.configure(text="A setzen")
            mini_datum_setzen(tag)
            return
        start = auswahl_start[0]
        ende = auswahl_ende[0]
        if start is None:
            _setze_zeitraum(tag, None)
        elif ende is None:
            if tag < start:
                _setze_zeitraum(tag, start)
            else:
                _setze_zeitraum(start, tag)
        else:
            _setze_zeitraum(tag, None)
        mini_datum_setzen(tag)

    mini_datum_setzen = mini_monat_in(
        aussen,
        mitte_datum=dt.date.today(),
        locale=locale,
        on_tag=_kalender_tag_geklickt,
        tag_stil_fn=_tag_stil_fuer_kalender,
    )
    mini_datum_setzen(dt.date.today())

    form = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    form.pack(fill=tk.X, pady=(6, 0))

    felder: list[tuple[str, tk.StringVar]] = [
        ("app.krankmeldung.start_label", start_var),
        ("app.krankmeldung.ende_label", ende_var),
        ("app.krankmeldung.notiz_label", notiz_var),
    ]
    feld_labels: list[tk.Label] = []
    for schluessel, var in felder:
        zeile = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
        zeile.pack(fill=tk.X, pady=(0, 6))
        label = tk.Label(
            zeile,
            text=get_string(schluessel, locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            anchor=tk.W,
            justify=tk.LEFT,
            wraplength=320,
        )
        label.pack(fill=tk.X)
        tk.Entry(zeile, textvariable=var).pack(fill=tk.X, pady=(2, 0))
        feld_labels.append(label)

    arzt_zeile = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    arzt_zeile.pack(fill=tk.X, pady=(0, 6))
    arzt_label = tk.Label(
        arzt_zeile,
        text="Arzt:",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=320,
    )
    arzt_label.pack(fill=tk.X)
    arzt_menu = tk.OptionMenu(arzt_zeile, arzt_auswahl_var, "")
    arzt_menu.pack(fill=tk.X, pady=(2, 4))
    tk.Button(
        arzt_zeile,
        text="Arzt anlegen",
        command=_arzt_anlegen_dialog,
        font=("Segoe UI", 9),
        padx=8,
        pady=2,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        activeforeground=kf.TEXT_ZEIT,
    ).pack(anchor=tk.W)
    feld_labels.append(arzt_label)

    termin_art_zeile = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    termin_art_zeile.pack(fill=tk.X, pady=(0, 6))
    termin_art_label = tk.Label(
        termin_art_zeile,
        text="Termin-Art:",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=320,
    )
    termin_art_label.pack(fill=tk.X)
    tk.OptionMenu(
        termin_art_zeile,
        termin_art_var,
        "wiedervorstellung",
        "nachkontrolle",
    ).pack(fill=tk.X, pady=(2, 0))
    feld_labels.append(termin_art_label)

    arzttermin_zeile = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    arzttermin_zeile.pack(fill=tk.X, pady=(0, 6))
    arzttermin_label = tk.Label(
        arzttermin_zeile,
        text="Arzttermin (Datum + Uhrzeit):",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=320,
    )
    arzttermin_label.pack(fill=tk.X)
    arzttermin_eingabe = tk.Frame(arzttermin_zeile, bg=kf.HINTERGRUND_FENSTER)
    arzttermin_eingabe.pack(fill=tk.X, pady=(2, 0))
    tk.Entry(arzttermin_eingabe, textvariable=arzt_var).pack(
        side=tk.LEFT, fill=tk.X, expand=True
    )
    tk.Entry(arzttermin_eingabe, textvariable=arztzeit_var, width=8).pack(side=tk.LEFT, padx=(6, 0))
    a_setzen_btn = tk.Button(
        arzttermin_eingabe,
        text="A setzen",
        command=lambda: (
            a_setzen_modus.__setitem__(0, not a_setzen_modus[0]),
            a_setzen_btn.configure(text="A setzen (aktiv)" if a_setzen_modus[0] else "A setzen"),
        ),
        font=("Segoe UI", 9),
        padx=8,
        pady=2,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg="#1565C0",
        fg="#FFFFFF",
        activebackground="#0D47A1",
        activeforeground="#FFFFFF",
    )
    a_setzen_btn.pack(side=tk.LEFT, padx=(6, 0))
    feld_labels.append(arzttermin_label)

    format_label = tk.Label(
        form,
        text=f"{get_string('app.krankmeldung.format_hinweis', locale)} | Zeitformat: HH:MM",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        font=("Segoe UI", 9),
        wraplength=320,
    )
    format_label.pack(fill=tk.X, pady=(0, 10))

    upload_rahmen = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    upload_rahmen.pack(fill=tk.X, pady=(0, 10))
    tk.Label(
        upload_rahmen,
        text=get_string("app.krankmeldung.upload_titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)
    tk.Label(
        upload_rahmen,
        textvariable=dokument_var,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=320,
        font=("Segoe UI", 9),
    ).pack(fill=tk.X, pady=(2, 6))
    upload_btn_rahmen = tk.Frame(upload_rahmen, bg=kf.HINTERGRUND_FENSTER)
    upload_btn_rahmen.pack(fill=tk.X)

    statistik_rahmen = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    statistik_rahmen.pack(fill=tk.X, pady=(0, 10))
    tk.Label(
        statistik_rahmen,
        text=get_string("app.krankmeldung.auswertung_krankheitstage", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)
    tk.Label(
        statistik_rahmen,
        textvariable=krankheitstage_var,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(0, 6))
    tk.Label(
        statistik_rahmen,
        text=get_string("app.krankmeldung.auswertung_tage_gesamt", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)
    tk.Label(
        statistik_rahmen,
        textvariable=tage_gesamt_var,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(anchor=tk.W)
    dokument_status_label = tk.Label(
        form,
        textvariable=dokument_status_var,
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=320,
        font=("Segoe UI", 9),
    )
    dokument_status_label.pack(fill=tk.X, pady=(0, 10))

    meta_box = tk.Frame(aussen, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0)
    meta_box.pack(fill=tk.X, pady=(0, 10))
    tk.Label(
        meta_box,
        textvariable=meta_modus_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.JETZT_ZEIGER,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, padx=10, pady=(8, 4))
    tk.Label(
        meta_box,
        textvariable=meta_erstellt_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, padx=10)
    tk.Label(
        meta_box,
        textvariable=meta_geaendert_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, padx=10)
    tk.Label(
        meta_box,
        textvariable=meta_anzahl_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        anchor=tk.W,
        justify=tk.LEFT,
    ).pack(fill=tk.X, padx=10, pady=(0, 8))

    verlauf_titel = tk.Label(
        aussen,
        text="Aenderungsverlauf",
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 11, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    )
    verlauf_titel.pack(fill=tk.X, pady=(4, 6))
    verlauf_liste = tk.Listbox(
        aussen,
        height=5,
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        selectbackground=kf.HINTERGRUND_ZEITLEISTE,
        selectforeground=kf.TEXT_ZEIT,
        bd=0,
        highlightthickness=0,
        activestyle="none",
    )
    verlauf_liste.pack(fill=tk.X, pady=(0, 8))

    status_box = tk.Frame(aussen, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0)
    status_box.pack(fill=tk.X, pady=(4, 12))
    status_hinweis_label = tk.Label(
        status_box,
        textvariable=status_hinweis_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.JETZT_ZEIGER,
        font=("Segoe UI", 10, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=300,
    )
    status_hinweis_label.pack(fill=tk.X, padx=10, pady=(8, 2))
    status_ende_label = tk.Label(
        status_box,
        textvariable=status_ende_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=300,
    )
    status_ende_label.pack(fill=tk.X, padx=10)
    status_arzt_label = tk.Label(
        status_box,
        textvariable=status_arzt_var,
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        anchor=tk.W,
        justify=tk.LEFT,
        wraplength=300,
    )
    status_arzt_label.pack(fill=tk.X, padx=10, pady=(0, 8))

    listentitel = tk.Label(
        aussen,
        text=get_string("app.krankmeldung.liste_titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 11, "bold"),
        anchor=tk.W,
        justify=tk.LEFT,
    )
    listentitel.pack(fill=tk.X, pady=(10, 6))

    liste_frame = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    liste_frame.pack(fill=tk.BOTH, expand=True)
    liste = tk.Listbox(
        liste_frame,
        height=8,
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        selectbackground=kf.HINTERGRUND_ZEITLEISTE,
        selectforeground=kf.TEXT_ZEIT,
        bd=0,
        highlightthickness=0,
        activestyle="none",
    )
    liste.pack(fill=tk.BOTH, expand=True)

    def _metadaten_anzeigen(eintrag_id: str | None) -> None:
        verlauf_liste.delete(0, tk.END)
        if not eintrag_id:
            meta_modus_var.set("Neue Krankmeldung")
            meta_erstellt_var.set("Angelegt: -")
            meta_geaendert_var.set("Geaendert: -")
            meta_anzahl_var.set("Aenderungen: 0")
            verlauf_liste.insert(tk.END, "Noch kein Aenderungsverlauf vorhanden.")
            return
        eintrag = eintrag_mit_id(eintrag_id)
        if eintrag is None:
            meta_modus_var.set("Krankmeldung")
            meta_erstellt_var.set("Angelegt: -")
            meta_geaendert_var.set("Geaendert: -")
            meta_anzahl_var.set("Aenderungen: -")
            return
        meta_modus_var.set("Krankmeldung bearbeiten")
        meta_erstellt_var.set(f"Angelegt: {_zeitpunkt_als_text(eintrag.erstellt_am)}")
        meta_geaendert_var.set(f"Geaendert: {_zeitpunkt_als_text(eintrag.geaendert_am)}")
        meta_anzahl_var.set(f"Aenderungen: {eintrag.aenderungsanzahl}")
        if not eintrag.aenderungen:
            verlauf_liste.insert(tk.END, "Noch keine inhaltliche Aenderung gespeichert.")
            return
        for aenderung in reversed(eintrag.aenderungen):
            teile: list[str] = []
            if (
                aenderung.start_datum_alt is not None
                and aenderung.start_datum_neu is not None
                and aenderung.start_datum_alt != aenderung.start_datum_neu
            ):
                teile.append(
                    "Von "
                    f"{_datum_als_text(aenderung.start_datum_alt)} -> "
                    f"{_datum_als_text(aenderung.start_datum_neu)}"
                )
            if (
                aenderung.ende_datum_alt is not None
                and aenderung.ende_datum_neu is not None
                and aenderung.ende_datum_alt != aenderung.ende_datum_neu
            ):
                teile.append(
                    "Bis "
                    f"{_datum_als_text(aenderung.ende_datum_alt)} -> "
                    f"{_datum_als_text(aenderung.ende_datum_neu)}"
                )
            if (
                aenderung.wiedervorstellung_datum_alt is not None
                and aenderung.wiedervorstellung_datum_neu is not None
                and aenderung.wiedervorstellung_datum_alt
                != aenderung.wiedervorstellung_datum_neu
            ):
                teile.append(
                    "Arzt "
                    f"{_datum_als_text(aenderung.wiedervorstellung_datum_alt)} -> "
                    f"{_datum_als_text(aenderung.wiedervorstellung_datum_neu)}"
                )
            if "notiz" in aenderung.felder:
                teile.append("Notiz geaendert")
            if "dokument_pfad" in aenderung.felder:
                teile.append("Dokument geaendert")
            text = f"{_zeitpunkt_als_text(aenderung.geaendert_am)} | " + ", ".join(
                teile or ["ohne sichtbare Datumsaenderung"]
            )
            verlauf_liste.insert(tk.END, text)

    def _formular_leeren() -> None:
        formular_sync_aktiv[0] = True
        bearbeitungs_id[0] = None
        _setze_zeitraum(None, None)
        arzt_var.set("")
        arztzeit_var.set("09:00")
        termin_art_var.set("wiedervorstellung")
        arzt_id_var.set("")
        notiz_var.set("")
        dokument_var.set("")
        dokument_status_var.set("")
        _arzt_optionen_aktualisieren()
        mini_datum_setzen(dt.date.today())
        formular_sync_aktiv[0] = False
        _tage_auswertung_aktualisieren()
        _metadaten_anzeigen(None)

    def _eintrag_ins_formular_laden(eintrag_id: str) -> None:
        eintrag = eintrag_mit_id(eintrag_id)
        if eintrag is None:
            return
        formular_sync_aktiv[0] = True
        bearbeitungs_id[0] = eintrag.id
        _setze_zeitraum(eintrag.start_datum, eintrag.ende_datum)
        arzt_var.set(_datum_als_text(eintrag.wiedervorstellung_datum))
        arztzeit_var.set(eintrag.arzttermin_zeit or "09:00")
        termin_art_var.set(eintrag.arzttermin_art or "wiedervorstellung")
        arzt_id_var.set(eintrag.arzt_id)
        _arzt_optionen_aktualisieren(eintrag.arzt_id or None)
        if not eintrag.arzt_id and eintrag.arzt_name_snapshot:
            arzt_auswahl_var.set(eintrag.arzt_name_snapshot)
        notiz_var.set(eintrag.notiz)
        dokument_var.set(eintrag.dokument_pfad)
        dokument_status_var.set(
            "Dokument fuer diese Krankmeldung gesetzt." if eintrag.dokument_pfad else ""
        )
        mini_datum_setzen(eintrag.start_datum)
        formular_sync_aktiv[0] = False
        _tage_auswertung_aktualisieren()
        _metadaten_anzeigen(eintrag.id)

    def _status_aktualisieren() -> None:
        eintraege = alle_eintraege()
        heute = dt.date.today()
        aktive = [e for e in eintraege if e.start_datum <= heute <= e.ende_datum]
        if aktive:
            aktuell = min(aktive, key=lambda e: (e.ende_datum, e.wiedervorstellung_datum))
            rest = (aktuell.ende_datum - heute).days
            status_hinweis_var.set(
                get_string("app.krankmeldung.status_aktiv", locale).format(tage=rest)
            )
            status_ende_var.set(
                get_string("app.krankmeldung.status_ende", locale).format(
                    datum=_datum_als_text(aktuell.ende_datum)
                )
            )
            status_arzt_var.set(
                get_string("app.krankmeldung.status_arzt", locale).format(
                    datum=_datum_als_text(aktuell.wiedervorstellung_datum)
                )
            )
            return

        zukuenftig = [e for e in eintraege if e.start_datum > heute]
        if zukuenftig:
            naechste = min(zukuenftig, key=lambda e: e.start_datum)
            status_hinweis_var.set(get_string("app.krankmeldung.status_zukuenftig", locale))
            status_ende_var.set(
                get_string("app.krankmeldung.status_start", locale).format(
                    datum=_datum_als_text(naechste.start_datum)
                )
            )
            status_arzt_var.set(
                get_string("app.krankmeldung.status_arzt", locale).format(
                    datum=_datum_als_text(naechste.wiedervorstellung_datum)
                )
            )
            return

        if eintraege:
            letztes = max(eintraege, key=lambda e: e.ende_datum)
            status_hinweis_var.set(get_string("app.krankmeldung.status_abgelaufen", locale))
            status_ende_var.set(
                get_string("app.krankmeldung.status_ende", locale).format(
                    datum=_datum_als_text(letztes.ende_datum)
                )
            )
            status_arzt_var.set(
                get_string("app.krankmeldung.status_arzt", locale).format(
                    datum=_datum_als_text(letztes.wiedervorstellung_datum)
                )
            )
            return

        status_hinweis_var.set(get_string("app.krankmeldung.status_leer", locale))
        status_ende_var.set("")
        status_arzt_var.set("")

    def _liste_aktualisieren() -> None:
        liste.delete(0, tk.END)
        listen_ids.clear()
        heute = dt.date.today()
        for e in alle_eintraege():
            if heute > e.ende_datum:
                status = get_string("app.krankmeldung.liste_status_abgelaufen", locale)
            elif e.start_datum <= heute <= e.ende_datum:
                status = get_string("app.krankmeldung.liste_status_aktiv", locale)
            else:
                status = get_string("app.krankmeldung.liste_status_geplant", locale)
            text = get_string("app.krankmeldung.liste_zeile", locale).format(
                start=_datum_als_text(e.start_datum),
                ende=_datum_als_text(e.ende_datum),
                arzt=_datum_als_text(e.wiedervorstellung_datum),
                status=status,
            )
            if e.arzt_name_snapshot:
                text = f"{text} | {e.arzt_name_snapshot}"
            if e.arzttermin_zeit:
                text = f"{text} {e.arzttermin_zeit}"
            if e.notiz:
                text = f"{text} - {e.notiz}"
            if e.dokument_pfad:
                text = f"{text} - {get_string('app.krankmeldung.liste_dokument', locale)}"
            liste.insert(tk.END, text)
            listen_ids.append(e.id)
        _status_aktualisieren()

    def _dokument_waehlen() -> None:
        pfad = filedialog.askopenfilename(
            parent=parent.winfo_toplevel(),
            title=get_string("app.krankmeldung.upload_datei_dialog", locale),
            filetypes=[
                (
                    get_string("app.krankmeldung.upload_datei_typen", locale),
                    "*.png *.jpg *.jpeg *.pdf *.heic *.webp",
                ),
                (get_string("app.krankmeldung.upload_alle_dateien", locale), "*.*"),
            ],
        )
        if not pfad:
            return
        try:
            ziel = _dokument_kopieren(pfad)
        except (OSError, FileNotFoundError) as exc:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                f"{get_string('app.krankmeldung.upload_fehler', locale)}: {exc}",
                parent=parent.winfo_toplevel(),
            )
            return
        dokument_var.set(ziel)
        dokument_status_var.set(get_string("app.krankmeldung.upload_status_gesetzt", locale))

    def _dokument_foto() -> None:
        try:
            ziel = _foto_aufnehmen_und_speichern()
        except RuntimeError:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                get_string("app.krankmeldung.upload_foto_fehler", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        except OSError as exc:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                f"{get_string('app.krankmeldung.upload_fehler', locale)}: {exc}",
                parent=parent.winfo_toplevel(),
            )
            return
        dokument_var.set(ziel)
        dokument_status_var.set(get_string("app.krankmeldung.upload_status_foto", locale))

    def _speichern() -> None:
        try:
            start_datum = _datum_parsen(start_var.get())
            ende_datum = _datum_parsen(ende_var.get())
            arzt_datum = _datum_parsen(arzt_var.get())
            _zeit_parsen(arztzeit_var.get())
        except ValueError:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                get_string("app.krankmeldung.fehler_format", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        termin_art = termin_art_var.get().strip() or "wiedervorstellung"
        arzt_id = arzt_id_var.get().strip()
        arzt_snapshot = _arzt_label(arzt_id)
        if not arzt_id or not arzt_snapshot:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                "Bitte einen Arzt auswaehlen oder neu anlegen.",
                parent=parent.winfo_toplevel(),
            )
            return
        if ende_datum < start_datum:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                get_string("app.krankmeldung.fehler_ende_vor_start", locale),
                parent=parent.winfo_toplevel(),
            )
            return
        if termin_art == "wiedervorstellung" and not (start_datum <= arzt_datum <= ende_datum):
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                "Wiedervorstellung muss innerhalb der AU liegen.",
                parent=parent.winfo_toplevel(),
            )
            return
        if termin_art == "nachkontrolle" and arzt_datum < ende_datum:
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                "Nachkontrolle muss am Enddatum oder spaeter liegen.",
                parent=parent.winfo_toplevel(),
            )
            return
        if bearbeitungs_id[0]:
            aktualisiert = eintrag_aktualisieren(
                bearbeitungs_id[0],
                start_datum=start_datum,
                ende_datum=ende_datum,
                wiedervorstellung_datum=arzt_datum,
                arzttermin_art=termin_art,
                arzttermin_zeit=arztzeit_var.get().strip(),
                arzt_id=arzt_id,
                arzt_name_snapshot=arzt_snapshot,
                notiz=notiz_var.get(),
                dokument_pfad=dokument_var.get(),
            )
            if aktualisiert is None:
                messagebox.showerror(
                    get_string("app.krankmeldung.fehler_titel", locale),
                    "Die Krankmeldung konnte nicht aktualisiert werden.",
                    parent=parent.winfo_toplevel(),
                )
                return
            ziel_id = aktualisiert.id
        else:
            ziel_id = eintrag_hinzufuegen(
                start_datum=start_datum,
                ende_datum=ende_datum,
                wiedervorstellung_datum=arzt_datum,
                arzttermin_art=termin_art,
                arzttermin_zeit=arztzeit_var.get().strip(),
                arzt_id=arzt_id,
                arzt_name_snapshot=arzt_snapshot,
                notiz=notiz_var.get(),
                dokument_pfad=dokument_var.get(),
            ).id
        _liste_aktualisieren()
        _eintrag_ins_formular_laden(ziel_id)
        if on_aenderung is not None:
            on_aenderung()

    def _listen_auswahl_uebernehmen(_event: tk.Event | None = None) -> None:
        auswahl = liste.curselection()
        if not auswahl:
            return
        index = int(auswahl[0])
        if 0 <= index < len(listen_ids):
            _eintrag_ins_formular_laden(listen_ids[index])

    def _loeschen() -> None:
        eintrag_id = bearbeitungs_id[0]
        if not eintrag_id:
            return
        eintrag = eintrag_mit_id(eintrag_id)
        if eintrag is None:
            _formular_leeren()
            _liste_aktualisieren()
            return
        bestaetigt = messagebox.askyesno(
            "Krankmeldung loeschen",
            "Diesen Krankenstand wirklich loeschen?\n\n"
            f"Von: {_datum_als_text(eintrag.start_datum)}\n"
            f"Bis: {_datum_als_text(eintrag.ende_datum)}",
            parent=parent.winfo_toplevel(),
        )
        if not bestaetigt:
            return
        if not eintrag_loeschen(eintrag_id):
            messagebox.showerror(
                get_string("app.krankmeldung.fehler_titel", locale),
                "Die Krankmeldung konnte nicht geloescht werden.",
                parent=parent.winfo_toplevel(),
            )
            return
        _formular_leeren()
        _liste_aktualisieren()
        if on_aenderung is not None:
            on_aenderung()

    def _tage_auswertung_aktualisieren() -> None:
        start_text = start_var.get().strip()
        ende_text = ende_var.get().strip()
        try:
            start_datum = _datum_parsen(start_text)
            ende_datum = _datum_parsen(ende_text)
        except ValueError:
            krankheitstage_var.set("0")
            tage_gesamt_var.set("0")
            return
        if ende_datum < start_datum:
            krankheitstage_var.set("0")
            tage_gesamt_var.set("0")
            return
        regelprofil, _ = arbeitseinstellungen_laden(
            standard_regelarbeit(),
            standard_arbeitspausen(),
        )
        gesamt = (ende_datum - start_datum).days + 1
        krankheitstage = 0
        for i in range(gesamt):
            tag = start_datum + dt.timedelta(days=i)
            if regelprofil.arbeitszeit_fuer_tag(tag) is not None:
                krankheitstage += 1
        krankheitstage_var.set(str(krankheitstage))
        tage_gesamt_var.set(str(gesamt))

    def _auswahl_aus_feldern_sync(_event: tk.Event | None = None) -> None:
        if formular_sync_aktiv[0]:
            return
        start_text = start_var.get().strip()
        ende_text = ende_var.get().strip()
        start_datum: dt.date | None = None
        ende_datum: dt.date | None = None
        if start_text:
            try:
                start_datum = _datum_parsen(start_text)
            except ValueError:
                start_datum = None
        if ende_text:
            try:
                ende_datum = _datum_parsen(ende_text)
            except ValueError:
                ende_datum = None
        auswahl_start[0] = start_datum
        auswahl_ende[0] = ende_datum
        fokus = ende_datum or start_datum or dt.date.today()
        mini_datum_setzen(fokus)
        _tage_auswertung_aktualisieren()

    tk.Button(
        upload_btn_rahmen,
        text=get_string("app.krankmeldung.upload_datei_btn", locale),
        command=_dokument_waehlen,
        font=("Segoe UI", 9),
        padx=8,
        pady=2,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        activeforeground=kf.TEXT_ZEIT,
    ).pack(side=tk.LEFT, padx=(0, 6))
    tk.Button(
        upload_btn_rahmen,
        text=get_string("app.krankmeldung.upload_foto_btn", locale),
        command=_dokument_foto,
        font=("Segoe UI", 9),
        padx=8,
        pady=2,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg=kf.HINTERGRUND_ZEITLEISTE,
        fg=kf.TEXT_ZEIT,
        activebackground=kf.RASTER_STUNDE,
        activeforeground=kf.TEXT_ZEIT,
    ).pack(side=tk.LEFT)

    aktionsleiste = tk.Frame(form, bg=kf.HINTERGRUND_FENSTER)
    aktionsleiste.pack(fill=tk.X)
    tk.Button(
        aktionsleiste,
        text="Neu",
        command=_formular_leeren,
        font=("Segoe UI", 10),
        padx=10,
        pady=3,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg="#2E7D32",
        fg="#FFFFFF",
        activebackground="#1B5E20",
        activeforeground="#FFFFFF",
    ).pack(side=tk.LEFT)
    tk.Button(
        aktionsleiste,
        text="Loeschen",
        command=_loeschen,
        font=("Segoe UI", 10),
        padx=10,
        pady=3,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg="#C62828",
        fg="#FFFFFF",
        activebackground="#8E0000",
        activeforeground="#FFFFFF",
    ).pack(side=tk.LEFT, padx=(6, 0))
    tk.Button(
        aktionsleiste,
        text=get_string("app.krankmeldung.btn_speichern", locale),
        command=_speichern,
        font=("Segoe UI", 10),
        padx=10,
        pady=3,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        bg="#1565C0",
        fg="#FFFFFF",
        activebackground="#0D47A1",
        activeforeground="#FFFFFF",
    ).pack(side=tk.RIGHT)

    start_var.trace_add("write", lambda *_: _auswahl_aus_feldern_sync())
    ende_var.trace_add("write", lambda *_: _auswahl_aus_feldern_sync())
    arzt_var.trace_add("write", lambda *_: _auswahl_aus_feldern_sync())
    liste.bind("<<ListboxSelect>>", _listen_auswahl_uebernehmen)
    liste.bind("<Double-Button-1>", _listen_auswahl_uebernehmen)

    def _layout_aktualisieren(_event: tk.Event | None = None) -> None:
        breite = max(220, wrap.winfo_width())
        umbruch = max(180, breite - 32)
        status_hinweis_label.configure(wraplength=umbruch - 20)
        status_ende_label.configure(wraplength=umbruch - 20)
        status_arzt_label.configure(wraplength=umbruch - 20)
        format_label.configure(wraplength=umbruch)
        dokument_status_label.configure(wraplength=umbruch)
        for lbl in feld_labels:
            lbl.configure(wraplength=umbruch)

    def _inhalt_configure(_event: tk.Event | None = None) -> None:
        _layout_aktualisieren()

    wrap.bind("<Configure>", lambda _e: _layout_aktualisieren())
    aussen.bind("<Configure>", _inhalt_configure)

    _arzt_optionen_aktualisieren()
    _tage_auswertung_aktualisieren()
    _liste_aktualisieren()
    if vorauswahl_id:
        _eintrag_ins_formular_laden(vorauswahl_id)
        if vorauswahl_id in listen_ids:
            index = listen_ids.index(vorauswahl_id)
            liste.selection_clear(0, tk.END)
            liste.selection_set(index)
            liste.see(index)
    else:
        _metadaten_anzeigen(None)
