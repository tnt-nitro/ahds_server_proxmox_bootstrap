"""Hauptfenster: links Kalender, Mitte Toolbox, rechts Icon-Leiste."""

from __future__ import annotations

from collections.abc import Callable
import datetime as dt

import tkinter as tk
import tkinter.font as tkfont

from locales import get_string

from modules.adressbuch import adressbuch_in
from modules.krankmeldung import krankmeldung_in
from modules.kalender.demo import kalender_demo_in
from modules.kalender_toolbox import mini_monat_in
from modules.kalender_zeitaufzeichnung import zeitaufzeichnung_kalender_in
from modules.konto import Benutzer, login_ansicht_in, stammdaten_sicherstellen
from modules.fenster_info import fenster_titel, zeitstempel_jetzt
from modules.schnellbild import schnellbild_in
from modules.schatzkiste import schatzkiste_in
from modules.sprachmemo import sprachmemo_in
from modules.theming.farben import kalender_farben
from modules.theming.modus import ist_darkmode, toggle_modus
from modules.version_info import load_version_info
from modules.app_shell.werkzeuge_speicher import (
    WERKZEUG_IDS,
    aktivitaet_laden,
    aktivitaet_toggle,
)

# Einfache Icon-Zeichen (Segoe UI); später durch Grafiken ersetzbar.
_SYM_USER = "\u263A"
_SYM_RUHE = "\u263E"
_SYM_KALENDER = "\u25A3"
_SYM_ZEITAUFZEICHNUNG = "\u23F1"
_SYM_KRANKMELDUNG = "\u2695"
_SYM_ROUTINEN = "\u21BB"
_SYM_KONTAKTE = "\u2630"
_SYM_ACHTSAM = "\u273F"
_SYM_EINKAUF = "\u229E"
_SYM_NOTIZ = "\u270E"
_SYM_ADRESSBUCH = "\u26EA"
_SYM_SPRACHMEMO = "\u266A"
_SYM_BILD = "\u25A6"
_SYM_SCHATZKISTE = "\u25A4"
_SYM_PLUS = "+"
_SYM_EINSTELLUNG = "\u2699"


def run_app(locale: str = "de") -> None:
    root = tk.Tk()
    version_info = load_version_info()
    root_geoeffnet_um = zeitstempel_jetzt()
    root.title(
        fenster_titel(
            basis_titel=get_string("app.shell.fenster_titel", locale),
            version_info=version_info,
            benutzer="Gast",
            geoeffnet_um=root_geoeffnet_um,
            locale=locale,
        )
    )
    root.geometry("1320x760")
    root.minsize(800, 480)

    kf = kalender_farben()
    root.configure(bg=kf.HINTERGRUND_FENSTER)

    haupt = tk.Frame(root, bg=kf.HINTERGRUND_FENSTER)
    haupt.pack(fill=tk.BOTH, expand=True)

    stammdaten_sicherstellen()

    aktueller_benutzer: list[Benutzer | None] = [None]
    login_container = tk.Frame(haupt, bg=kf.HINTERGRUND_FENSTER)
    main_content_ref: list[tk.Frame | None] = [None]
    sensibles_leeren_ref: list[Callable[[], None] | None] = [None]

    def bei_abmeldung() -> None:
        aktueller_benutzer[0] = None
        if main_content_ref[0] is not None:
            main_content_ref[0].pack_forget()
        if sensibles_leeren_ref[0] is not None:
            sensibles_leeren_ref[0]()
        login_container.pack(fill=tk.BOTH, expand=True)

    def shell_haupt_teil() -> None:
        nonlocal kf
        innen = tk.Frame(haupt, bg=kf.HINTERGRUND_FENSTER)
        main_content_ref[0] = innen

        kalender_bereich = tk.Frame(innen, bg=kf.HINTERGRUND_FENSTER)

        toolbox_rahmen = tk.Frame(
            innen,
            width=240,
            bg=kf.HINTERGRUND_BLATT,
            bd=0,
            highlightthickness=0,
        )
        toolbox_canvas = tk.Canvas(
            toolbox_rahmen,
            bg=kf.HINTERGRUND_FENSTER,
            bd=0,
            highlightthickness=0,
        )
        # Kein klassischer Scrollbalken — nur Mausrad / Touchpad (siehe _toolbox_mausrad*).
        toolbox_canvas.pack(fill=tk.BOTH, expand=True)
        toolbox_inhalt = tk.Frame(toolbox_canvas, bg=kf.HINTERGRUND_FENSTER)
        toolbox_window_id = toolbox_canvas.create_window(
            (0, 0),
            window=toolbox_inhalt,
            anchor=tk.NW,
        )
        toolbox_sichtbar: list[bool] = [False]
        toolbox_anteil = 0.20

        # Icon-Spalte, vertikal nur per Mausrad scrollen (ohne sichtbaren Balken).
        rail_icon_breite = 56
        rail_breite = rail_icon_breite
        rail = tk.Frame(
            innen, width=rail_breite, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0
        )
        rail.pack(side=tk.RIGHT, fill=tk.Y)
        rail.pack_propagate(False)

        rail_footer = tk.Frame(rail, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0)
        rail_footer.pack(side=tk.BOTTOM, fill=tk.X)

        rail_scroll_bereich = tk.Frame(rail, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0)
        rail_scroll_bereich.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        rail_canvas = tk.Canvas(
            rail_scroll_bereich,
            width=rail_icon_breite,
            bg=kf.HINTERGRUND_ZEITLEISTE,
            bd=0,
            highlightthickness=0,
        )
        rail_canvas.pack(fill=tk.BOTH, expand=True)

        rail_inhalt = tk.Frame(rail_canvas, bg=kf.HINTERGRUND_ZEITLEISTE, bd=0, highlightthickness=0)
        rail_window_id = rail_canvas.create_window((0, 0), window=rail_inhalt, anchor=tk.NW)
        kalender_bereich.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        icon_font = tkfont.Font(root, family="Segoe UI", size=16)
        klein_font = tkfont.Font(root, family="Segoe UI", size=11)

        aktives_tool: list[str | None] = [None]
        kalender_nach_modus: list[Callable[[], None] | None] = [None]
        kalender_ansicht_ref: list[object | None] = [None]
        krankmeldung_vorauswahl_id: list[str | None] = [None]
        kontakt_vorauswahl_id: list[str | None] = [None]
        rail_buttons: list[tuple[tk.Button, str]] = []

        def _ist_kind_von(widget: tk.Widget | None, ancestor: tk.Widget) -> bool:
            w = widget
            while w is not None:
                if w is ancestor:
                    return True
                parent_name = w.winfo_parent()
                if not parent_name:
                    break
                try:
                    w = w.nametowidget(parent_name)
                except KeyError:
                    break
            return False

        def toolbox_nach_oben() -> None:
            try:
                toolbox_canvas.yview_moveto(0.0)
            except tk.TclError:
                pass

        def kalender_darstellung_auffrischen() -> None:
            ansicht = kalender_ansicht_ref[0]
            if ansicht is None:
                return
            try:
                ansicht.darstellung_auffrischen()  # type: ignore[attr-defined]
            except Exception:
                pass

        def kalender_zu_datum(tag: dt.date) -> None:
            ansicht = kalender_ansicht_ref[0]
            if ansicht is not None:
                try:
                    ansicht.datum_setzen(tag)  # type: ignore[attr-defined]
                except Exception:
                    pass
            kalender_darstellung_auffrischen()

        def krankmeldung_oeffnen(eintrag_id: str | None) -> None:
            krankmeldung_vorauswahl_id[0] = eintrag_id
            tool_zeigen("krankmeldung", force=True)

        def _bei_krankmeldung_oeffnen(_event: tk.Event | None = None) -> None:
            krankmeldung_oeffnen(getattr(root, "_ahds_krankmeldung_id", None))

        root.bind("<<KrankmeldungOeffnen>>", _bei_krankmeldung_oeffnen)

        def _bei_kontakt_oeffnen(_event: tk.Event | None = None) -> None:
            kid = getattr(root, "_ahds_kontakt_id", None)
            kontakt_vorauswahl_id[0] = str(kid).strip() if kid else None
            tool_zeigen("adressbuch", force=True)

        root.bind("<<KontaktOeffnen>>", _bei_kontakt_oeffnen)

        def _toolbox_scrollregion_sync(_e: tk.Event | None = None) -> None:
            try:
                toolbox_canvas.update_idletasks()
                breite = max(toolbox_canvas.winfo_width(), toolbox_inhalt.winfo_reqwidth(), 1)
                hoehe = max(toolbox_canvas.winfo_height(), toolbox_inhalt.winfo_reqheight(), 1)
                toolbox_canvas.configure(scrollregion=(0, 0, breite, hoehe))
            except tk.TclError:
                pass

        def _toolbox_canvas_breite_sync(_e: tk.Event | None = None) -> None:
            try:
                breite = toolbox_canvas.winfo_width()
                if breite > 1:
                    toolbox_canvas.itemconfigure(toolbox_window_id, width=breite)
            except tk.TclError:
                pass

        _SCROLL_FACTOR = 4

        def _toolbox_mausrad_scroll(schritte: int) -> None:
            if not toolbox_sichtbar[0] or schritte == 0:
                return
            try:
                for _ in range(_SCROLL_FACTOR):
                    toolbox_canvas.yview_scroll(schritte, "units")
            except tk.TclError:
                pass

        def _toolbox_mausrad(_event: tk.Event) -> str:
            if not toolbox_sichtbar[0]:
                return "break"
            delta = int(getattr(_event, "delta", 0))
            if delta == 0:
                return "break"
            _toolbox_mausrad_scroll(-1 if delta > 0 else 1)
            return "break"

        def _toolbox_mausrad_linux_hoch(_event: tk.Event) -> str:
            _toolbox_mausrad_scroll(-1)
            return "break"

        def _toolbox_mausrad_linux_runter(_event: tk.Event) -> str:
            _toolbox_mausrad_scroll(1)
            return "break"

        def _rail_scrollregion_sync(_e: tk.Event | None = None) -> None:
            try:
                rail_canvas.update_idletasks()
                breite = max(rail_canvas.winfo_width(), rail_inhalt.winfo_reqwidth(), 1)
                hoehe = max(rail_canvas.winfo_height(), rail_inhalt.winfo_reqheight(), 1)
                rail_canvas.configure(scrollregion=(0, 0, breite, hoehe))
            except tk.TclError:
                pass

        def _rail_canvas_breite_sync(_e: tk.Event | None = None) -> None:
            try:
                breite = rail_canvas.winfo_width()
                if breite > 1:
                    rail_canvas.itemconfigure(rail_window_id, width=breite)
            except tk.TclError:
                pass

        def _rail_mausrad_scroll(schritte: int) -> None:
            if schritte == 0:
                return
            try:
                for _ in range(_SCROLL_FACTOR):
                    rail_canvas.yview_scroll(schritte, "units")
            except tk.TclError:
                pass

        def _rail_mausrad(_event: tk.Event) -> str:
            delta = int(getattr(_event, "delta", 0))
            if delta == 0:
                return "break"
            _rail_mausrad_scroll(-1 if delta > 0 else 1)
            return "break"

        def _rail_mausrad_linux_hoch(_event: tk.Event) -> str:
            _rail_mausrad_scroll(-1)
            return "break"

        def _rail_mausrad_linux_runter(_event: tk.Event) -> str:
            _rail_mausrad_scroll(1)
            return "break"

        def _globales_mausrad(_event: tk.Event) -> str | None:
            try:
                widget_unter_cursor = root.winfo_containing(
                    root.winfo_pointerx(), root.winfo_pointery()
                )
            except tk.TclError:
                return None
            if toolbox_sichtbar[0] and _ist_kind_von(widget_unter_cursor, toolbox_rahmen):
                return _toolbox_mausrad(_event)
            if _ist_kind_von(widget_unter_cursor, rail):
                return _rail_mausrad(_event)
            return None

        def _globales_mausrad_linux_hoch(_event: tk.Event) -> str | None:
            try:
                widget_unter_cursor = root.winfo_containing(
                    root.winfo_pointerx(), root.winfo_pointery()
                )
            except tk.TclError:
                return None
            if toolbox_sichtbar[0] and _ist_kind_von(widget_unter_cursor, toolbox_rahmen):
                return _toolbox_mausrad_linux_hoch(_event)
            if _ist_kind_von(widget_unter_cursor, rail):
                return _rail_mausrad_linux_hoch(_event)
            return None

        def _globales_mausrad_linux_runter(_event: tk.Event) -> str | None:
            try:
                widget_unter_cursor = root.winfo_containing(
                    root.winfo_pointerx(), root.winfo_pointery()
                )
            except tk.TclError:
                return None
            if toolbox_sichtbar[0] and _ist_kind_von(widget_unter_cursor, toolbox_rahmen):
                return _toolbox_mausrad_linux_runter(_event)
            if _ist_kind_von(widget_unter_cursor, rail):
                return _rail_mausrad_linux_runter(_event)
            return None

        toolbox_inhalt.bind("<Configure>", _toolbox_scrollregion_sync)
        toolbox_canvas.bind("<Configure>", _toolbox_canvas_breite_sync)
        toolbox_canvas.bind("<MouseWheel>", _toolbox_mausrad)
        toolbox_inhalt.bind("<MouseWheel>", _toolbox_mausrad)
        toolbox_canvas.bind("<Button-4>", _toolbox_mausrad_linux_hoch)
        toolbox_canvas.bind("<Button-5>", _toolbox_mausrad_linux_runter)
        toolbox_inhalt.bind("<Button-4>", _toolbox_mausrad_linux_hoch)
        toolbox_inhalt.bind("<Button-5>", _toolbox_mausrad_linux_runter)

        rail_inhalt.bind("<Configure>", _rail_scrollregion_sync)
        rail_canvas.bind("<Configure>", _rail_canvas_breite_sync)
        rail_canvas.bind("<MouseWheel>", _rail_mausrad)
        rail_inhalt.bind("<MouseWheel>", _rail_mausrad)
        rail_canvas.bind("<Button-4>", _rail_mausrad_linux_hoch)
        rail_canvas.bind("<Button-5>", _rail_mausrad_linux_runter)
        rail_inhalt.bind("<Button-4>", _rail_mausrad_linux_hoch)
        rail_inhalt.bind("<Button-5>", _rail_mausrad_linux_runter)

        root.bind_all("<MouseWheel>", _globales_mausrad, add="+")
        root.bind_all("<Button-4>", _globales_mausrad_linux_hoch, add="+")
        root.bind_all("<Button-5>", _globales_mausrad_linux_runter, add="+")

        def toolbox_leeren() -> None:
            for w in toolbox_inhalt.winfo_children():
                w.destroy()
            toolbox_nach_oben()
            _toolbox_scrollregion_sync()

        def toolbox_breite_aktualisieren(_e: tk.Event | None = None) -> None:
            gesamt = max(1, haupt.winfo_width() - rail_breite)
            breite = int(gesamt * toolbox_anteil)
            breite = max(220, min(380, breite))
            toolbox_rahmen.configure(width=breite)

        def toolbox_anzeigen() -> None:
            if toolbox_sichtbar[0]:
                return
            toolbox_rahmen.pack(side=tk.RIGHT, fill=tk.Y, after=rail)
            toolbox_rahmen.pack_propagate(False)
            toolbox_sichtbar[0] = True
            toolbox_breite_aktualisieren()
            toolbox_nach_oben()
            _toolbox_scrollregion_sync()

        def toolbox_verstecken() -> None:
            if not toolbox_sichtbar[0]:
                return
            toolbox_rahmen.pack_forget()
            toolbox_sichtbar[0] = False

        def btn_style_aktiv(ist_aktiv: bool) -> dict[str, object]:
            if ist_aktiv:
                return {
                    "bg": kf.HINTERGRUND_BLATT,
                    "fg": kf.JETZT_ZEIGER,
                    "activebackground": kf.HINTERGRUND_BLATT,
                    "activeforeground": kf.JETZT_ZEIGER,
                }
            return {
                "bg": kf.HINTERGRUND_ZEITLEISTE,
                "fg": kf.TEXT_ZEIT,
                "activebackground": kf.RASTER_STUNDE,
                "activeforeground": kf.TEXT_ZEIT,
            }

        def rail_highlight() -> None:
            for b, mid in rail_buttons:
                b.configure(**btn_style_aktiv(mid == aktives_tool[0]))

        def tool_bezeichnung(modul_id: str) -> str:
            return {
                "user": get_string("app.shell.tooltip_user", locale),
                "ruhe": get_string("app.shell.tooltip_ruhe", locale),
                "kalender": get_string("app.shell.tooltip_kalender", locale),
                "zeitaufzeichnung": get_string("app.shell.tooltip_zeitaufzeichnung", locale),
                "krankmeldung": get_string("app.shell.tooltip_krankmeldung", locale),
                "adressbuch": get_string("app.shell.tooltip_kontakte_modul", locale),
                "routinen": get_string("app.shell.tooltip_routinen", locale),
                "kontakte": get_string("app.shell.tooltip_kontakte_modul", locale),
                "achtsamkeit": get_string("app.shell.tooltip_achtsamkeit", locale),
                "einkaufen": get_string("app.shell.tooltip_einkaufen", locale),
                "sprachmemo": get_string("app.shell.tooltip_sprachmemo", locale),
                "schnellbild": get_string("app.shell.tooltip_schnellbild", locale),
                "schatzkiste": get_string("app.shell.tooltip_schatzkiste", locale),
                "notizen": get_string("app.shell.tooltip_notizen", locale),
                "plus": get_string("app.shell.tooltip_modul_hinzufuegen", locale),
            }.get(modul_id, "Modul")

        def tool_einstellungen_klick(modul_id: str) -> None:
            win = tk.Toplevel(root)
            win.title(
                fenster_titel(
                    basis_titel=f"Einstellungen - {tool_bezeichnung(modul_id)}",
                    version_info=version_info,
                    benutzer=aktueller_benutzer[0].name if aktueller_benutzer[0] else "Gast",
                    geoeffnet_um=zeitstempel_jetzt(),
                    locale=locale,
                )
            )
            win.configure(bg=kf.HINTERGRUND_FENSTER)
            win.geometry("360x180")
            tk.Label(
                win,
                text=f"Einstellungen fuer {tool_bezeichnung(modul_id)}",
                bg=kf.HINTERGRUND_FENSTER,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 11, "bold"),
                anchor=tk.W,
                justify=tk.LEFT,
                padx=16,
                pady=12,
            ).pack(fill=tk.X)
            tk.Label(
                win,
                text="Hier koennen spaeter tool-spezifische Optionen gepflegt werden.",
                bg=kf.HINTERGRUND_FENSTER,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 10),
                wraplength=320,
                justify=tk.LEFT,
                padx=16,
                pady=(0, 12),
            ).pack(fill=tk.X)

        def toolbox_bereich_mit_titel(modul_id: str) -> tk.Frame:
            kopf = tk.Frame(toolbox_inhalt, bg=kf.HINTERGRUND_FENSTER)
            kopf.pack(fill=tk.X, padx=12, pady=(2, 8))
            tk.Button(
                kopf,
                text=_SYM_EINSTELLUNG,
                font=("Segoe UI", 10),
                width=2,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                command=lambda: tool_einstellungen_klick(modul_id),
                bg=kf.HINTERGRUND_FENSTER,
                fg=kf.TEXT_ZEIT,
                activebackground=kf.HINTERGRUND_FENSTER,
                activeforeground=kf.JETZT_ZEIGER,
            ).pack(side=tk.RIGHT)
            tk.Label(
                kopf,
                text="Toolbox",
                bg=kf.HINTERGRUND_FENSTER,
                fg="#000000",
                font=("Segoe UI", 9),
                anchor=tk.E,
                justify=tk.RIGHT,
            ).pack(side=tk.RIGHT, padx=(0, 4))
            inhalt = tk.Frame(toolbox_inhalt, bg=kf.HINTERGRUND_FENSTER)
            inhalt.pack(fill=tk.BOTH, expand=True)
            return inhalt

        def tool_zeigen(modul_id: str, force: bool = False) -> None:
            if not force and aktives_tool[0] == modul_id:
                aktives_tool[0] = None
                toolbox_leeren()
                toolbox_verstecken()
                rail_highlight()
                return
            if modul_id == "kalender":
                aktives_tool[0] = modul_id
                toolbox_anzeigen()
                toolbox_leeren()
                toolbox_bereich = toolbox_bereich_mit_titel(modul_id)
                obere_zone = tk.Frame(
                    toolbox_bereich, bg=kalender_farben().HINTERGRUND_FENSTER
                )
                obere_zone.pack(fill=tk.X)
                untere_zone = tk.Frame(
                    toolbox_bereich, bg=kalender_farben().HINTERGRUND_FENSTER
                )
                untere_zone.pack(fill=tk.BOTH, expand=True)

                def on_tag(datum: dt.date) -> None:
                    try:
                        if kalender_ansicht_ref[0] is not None:
                            kalender_ansicht_ref[0].datum_setzen(datum)  # type: ignore[attr-defined]
                    except tk.TclError:
                        pass

                mitte_datum = dt.date.today()
                if kalender_ansicht_ref[0] is not None:
                    try:
                        mitte_datum = kalender_ansicht_ref[0].datum  # type: ignore[attr-defined]
                    except Exception:
                        pass
                mini_monat_in(
                    obere_zone,
                    mitte_datum=mitte_datum,
                    locale=locale,
                    on_tag=on_tag,
                )
                rail_highlight()
                return
            aktives_tool[0] = modul_id
            toolbox_anzeigen()
            toolbox_leeren()
            toolbox_bereich = toolbox_bereich_mit_titel(modul_id)
            if modul_id == "user":
                b = aktueller_benutzer[0]
                if b is None:
                    return
                tk.Label(
                    toolbox_bereich,
                    text=get_string("app.konto.profil_eingeloggt_als", locale).format(
                        name=b.name
                    ),
                    bg=kf.HINTERGRUND_FENSTER,
                    fg=kf.TEXT_ZEIT,
                    wraplength=320,
                    justify=tk.LEFT,
                    font=("Segoe UI", 10),
                    padx=16,
                ).pack(anchor=tk.W, pady=(8, 4))
                tk.Label(
                    toolbox_bereich,
                    text=get_string("app.konto.profil_email", locale).format(email=b.email),
                    bg=kf.HINTERGRUND_FENSTER,
                    fg=kf.TEXT_ZEIT,
                    wraplength=320,
                    justify=tk.LEFT,
                    font=("Segoe UI", 10),
                    padx=16,
                ).pack(anchor=tk.W, pady=(0, 16))
                tk.Button(
                    toolbox_bereich,
                    text=get_string("app.konto.btn_abmelden", locale),
                    command=bei_abmeldung,
                    font=("Segoe UI", 10),
                    padx=12,
                    pady=4,
                    cursor="hand2",
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    activebackground=kf.RASTER_STUNDE,
                    activeforeground=kf.TEXT_ZEIT,
                    relief=tk.FLAT,
                ).pack(anchor=tk.CENTER, pady=(0, 16))
                rail_highlight()
                return
            if modul_id == "ruhe":
                tk.Label(
                    toolbox_bereich,
                    text=get_string("app.shell.ruhe_ansicht_text", locale),
                    bg=kf.HINTERGRUND_BLATT,
                    fg=kf.TEXT_ZEIT,
                    font=("Segoe UI", 16),
                    wraplength=320,
                    justify=tk.CENTER,
                ).pack(expand=True)
                rail_highlight()
                return
            if modul_id == "zeitaufzeichnung":
                zeitaufzeichnung_kalender_in(toolbox_bereich, locale)
                rail_highlight()
                return
            if modul_id == "krankmeldung":
                krankmeldung_in(
                    toolbox_bereich,
                    locale,
                    vorauswahl_id=krankmeldung_vorauswahl_id[0],
                    on_aenderung=kalender_darstellung_auffrischen,
                )
                rail_highlight()
                return
            if modul_id in ("adressbuch", "kontakte"):
                adressbuch_in(
                    toolbox_bereich,
                    locale,
                    vorauswahl_id=kontakt_vorauswahl_id[0],
                    on_aenderung=kalender_darstellung_auffrischen,
                    on_zum_kalender=kalender_zu_datum,
                )
                kontakt_vorauswahl_id[0] = None
                rail_highlight()
                return
            if modul_id == "sprachmemo":
                sprachmemo_in(toolbox_bereich, locale)
                rail_highlight()
                return
            if modul_id == "schnellbild":
                schnellbild_in(toolbox_bereich, locale)
                rail_highlight()
                return
            if modul_id == "schatzkiste":
                schatzkiste_in(toolbox_bereich, locale)
                rail_highlight()
                return
            if modul_id == "plus":
                plus_werkzeuge_panel(toolbox_bereich)
                rail_highlight()
                return
            tk.Label(
                toolbox_bereich,
                text=get_string("app.shell.modul_entwicklung", locale),
                bg=kf.HINTERGRUND_BLATT,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 14),
                wraplength=320,
                justify=tk.CENTER,
            ).pack(expand=True)
            rail_highlight()

        class ToolTip:
            """Kleines Hilfs-Tooltip (ohne externes Paket)."""

            def __init__(self, widget: tk.Widget, text: str) -> None:
                self._widget = widget
                self._text = text
                self._tip: tk.Toplevel | None = None
                widget.bind("<Enter>", self._ein)
                widget.bind("<Leave>", self._aus)

            def _ein(self, _e: tk.Event | None = None) -> None:
                if self._tip is not None:
                    return
                x = self._widget.winfo_rootx() + 8
                y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
                self._tip = tk.Toplevel(self._widget)
                self._tip.wm_overrideredirect(True)
                self._tip.wm_geometry(f"+{x}+{y}")
                kf2 = kalender_farben()
                f = tk.Frame(self._tip, bg=kf2.TEXT_ZEIT, bd=1, highlightthickness=0)
                f.pack()
                tk.Label(
                    f,
                    text=self._text,
                    bg=kf2.TEXT_ZEIT,
                    fg=kf2.HINTERGRUND_BLATT,
                    font=("Segoe UI", 9),
                    padx=6,
                    pady=2,
                ).pack()

            def _aus(self, _e: tk.Event | None = None) -> None:
                if self._tip is not None:
                    try:
                        self._tip.destroy()
                    except tk.TclError:
                        pass
                    self._tip = None

        b_user = tk.Button(
            rail_inhalt,
            text=_SYM_USER,
            font=icon_font,
            width=3,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: tool_zeigen("user"),
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            activebackground=kf.RASTER_STUNDE,
        )
        b_user.pack(fill=tk.X, pady=(8, 0), padx=4)
        ToolTip(b_user, get_string("app.shell.tooltip_user", locale))
        rail_buttons.append((b_user, "user"))

        rail_ruhe = tk.Button(
            rail_inhalt,
            text=_SYM_RUHE,
            font=icon_font,
            width=3,
            height=1,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=lambda: tool_zeigen("ruhe"),
            **btn_style_aktiv(False),
        )
        rail_ruhe.pack(fill=tk.X, pady=(4, 0), padx=4)
        ToolTip(rail_ruhe, get_string("app.shell.tooltip_ruhe", locale))
        rail_buttons.append((rail_ruhe, "ruhe"))

        trenn = tk.Frame(rail_inhalt, height=1, bg=kf.RASTER_STUNDE)
        trenn.pack(fill=tk.X, padx=6, pady=8)

        rail_module_bereich = tk.Frame(rail_inhalt, bg=kf.HINTERGRUND_ZEITLEISTE)
        rail_module_bereich.pack(fill=tk.X)

        eintraege: list[tuple[str, str, str]] = [
            (_SYM_KALENDER, "kalender", get_string("app.shell.tooltip_kalender", locale)),
            (
                _SYM_ZEITAUFZEICHNUNG,
                "zeitaufzeichnung",
                get_string("app.shell.tooltip_zeitaufzeichnung", locale),
            ),
            (
                _SYM_KRANKMELDUNG,
                "krankmeldung",
                get_string("app.shell.tooltip_krankmeldung", locale),
            ),
            (
                _SYM_ADRESSBUCH,
                "adressbuch",
                get_string("app.shell.tooltip_kontakte_modul", locale),
            ),
            (_SYM_ROUTINEN, "routinen", get_string("app.shell.tooltip_routinen", locale)),
            (_SYM_KONTAKTE, "kontakte", get_string("app.shell.tooltip_kontakte_modul", locale)),
            (_SYM_ACHTSAM, "achtsamkeit", get_string("app.shell.tooltip_achtsamkeit", locale)),
            (_SYM_EINKAUF, "einkaufen", get_string("app.shell.tooltip_einkaufen", locale)),
            (_SYM_SPRACHMEMO, "sprachmemo", get_string("app.shell.tooltip_sprachmemo", locale)),
            (_SYM_BILD, "schnellbild", get_string("app.shell.tooltip_schnellbild", locale)),
            (_SYM_SCHATZKISTE, "schatzkiste", get_string("app.shell.tooltip_schatzkiste", locale)),
            (_SYM_NOTIZ, "notizen", get_string("app.shell.tooltip_notizen", locale)),
        ]

        def rail_modul_button(sym: str, modul_id: str, tooltip: str) -> tk.Button:
            def klick() -> None:
                tool_zeigen(modul_id)

            b = tk.Button(
                rail_module_bereich,
                text=sym,
                font=icon_font,
                width=3,
                height=1,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                command=klick,
                **btn_style_aktiv(False),
            )
            b.pack(fill=tk.X, pady=(4, 0), padx=4)
            ToolTip(b, tooltip)
            rail_buttons.append((b, modul_id))
            return b

        def rail_module_bereich_neu_aufbauen() -> None:
            for w in rail_module_bereich.winfo_children():
                w.destroy()
            rail_buttons[:] = [p for p in rail_buttons if p[1] not in WERKZEUG_IDS]
            aktiv = aktivitaet_laden()
            if aktives_tool[0] in WERKZEUG_IDS and not aktiv.get(
                str(aktives_tool[0]), True
            ):
                aktives_tool[0] = None
                toolbox_leeren()
                toolbox_verstecken()
            for sym, mid, tip in eintraege:
                if aktiv.get(mid, True):
                    rail_modul_button(sym, mid, tip)

        def plus_werkzeuge_panel(bereich: tk.Frame) -> None:
            """Alle Werkzeuge mit Kurztext; gruen = in der Leiste aktiv."""
            kf_plus = kalender_farben()
            tk.Label(
                bereich,
                text=get_string("app.shell.plus_panel_titel", locale),
                bg=kf_plus.HINTERGRUND_FENSTER,
                fg=kf_plus.TEXT_ZEIT,
                font=("Segoe UI", 11, "bold"),
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=300,
            ).pack(fill=tk.X, padx=12, pady=(4, 8))
            aktiv = aktivitaet_laden()
            kurz_font = tkfont.Font(root, family="Segoe UI", size=9)

            def zeile_farben(ist_aktiv: bool) -> dict[str, object]:
                if ist_aktiv:
                    return {
                        "bg": kf_plus.REGELARBEIT_FLACHE,
                        "fg": kf_plus.TEXT_ZEIT,
                        "activebackground": kf_plus.REGELARBEIT_FLACHE,
                        "activeforeground": kf_plus.TEXT_ZEIT,
                    }
                return {
                    "bg": kf_plus.HINTERGRUND_FENSTER,
                    "fg": kf_plus.TEXT_ZEIT,
                    "activebackground": kf_plus.RASTER_STUNDE,
                    "activeforeground": kf_plus.TEXT_ZEIT,
                }

            for sym, mid, tip in eintraege:
                ist_aktiv = aktiv.get(mid, True)
                farben = zeile_farben(ist_aktiv)
                kurz = get_string(f"app.shell.werkzeug.kurz.{mid}", locale)
                zeile = tk.Frame(bereich, bg=farben["bg"], bd=0, highlightthickness=0)
                zeile.pack(fill=tk.X, padx=8, pady=2)

                def klick_toggle(m: str) -> None:
                    aktivitaet_toggle(m)
                    rail_module_bereich_neu_aufbauen()
                    _rail_scrollregion_sync()
                    tool_zeigen("plus", force=True)

                tk.Label(
                    zeile,
                    text=sym,
                    font=icon_font,
                    bg=farben["bg"],
                    fg=farben["fg"],
                    width=2,
                    anchor=tk.CENTER,
                ).pack(side=tk.LEFT, padx=(4, 6))
                btn = tk.Button(
                    zeile,
                    text=kurz,
                    font=kurz_font,
                    anchor=tk.W,
                    relief=tk.FLAT,
                    bd=0,
                    highlightthickness=0,
                    cursor="hand2",
                    command=lambda m=mid: klick_toggle(m),
                    **farben,
                )
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)
                ToolTip(btn, tip)

        rail_module_bereich_neu_aufbauen()

        def modus_symbol_aktuell() -> str:
            return "\u263e" if not ist_darkmode() else "\u2600"

        def bei_modus_klick() -> None:
            nonlocal kf
            toggle_modus()
            kf = kalender_farben()
            root.configure(bg=kf.HINTERGRUND_FENSTER)
            haupt.configure(bg=kf.HINTERGRUND_FENSTER)
            innen.configure(bg=kf.HINTERGRUND_FENSTER)
            kalender_bereich.configure(bg=kf.HINTERGRUND_FENSTER)
            toolbox_rahmen.configure(
                bg=kf.HINTERGRUND_BLATT,
            )
            toolbox_canvas.configure(bg=kf.HINTERGRUND_FENSTER)
            toolbox_inhalt.configure(bg=kf.HINTERGRUND_FENSTER)
            rail.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            rail_footer.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            rail_scroll_bereich.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            rail_canvas.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            rail_inhalt.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            rail_module_bereich.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
            trenn.configure(bg=kf.RASTER_STUNDE)
            b_user.configure(
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                activebackground=kf.RASTER_STUNDE,
            )
            rail_ruhe.configure(
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                activebackground=kf.RASTER_STUNDE,
            )
            modus_btn.configure(
                text=modus_symbol_aktuell(),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                activebackground=kf.RASTER_STUNDE,
            )
            b_plus.configure(
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                activebackground=kf.RASTER_STUNDE,
            )
            rail_highlight()
            if kalender_nach_modus[0] is not None:
                kalender_nach_modus[0]()
            if aktives_tool[0]:
                tool_zeigen(aktives_tool[0], force=True)

        modus_btn = tk.Button(
            rail_footer,
            text=modus_symbol_aktuell(),
            font=icon_font,
            width=3,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            command=bei_modus_klick,
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            activebackground=kf.RASTER_STUNDE,
        )
        modus_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 4), padx=4)
        ToolTip(modus_btn, get_string("app.shell.tooltip_erscheinungsmodus", locale))

        b_plus = tk.Button(
            rail_footer,
            text=_SYM_PLUS,
            font=klein_font,
            width=3,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            activebackground=kf.RASTER_STUNDE,
            command=lambda: tool_zeigen("plus"),
        )
        b_plus.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 4), padx=4)
        ToolTip(b_plus, get_string("app.shell.tooltip_modul_hinzufuegen", locale))
        rail_buttons.append((b_plus, "plus"))

        _rail_scrollregion_sync()

        kalender_handle = kalender_demo_in(kalender_bereich, locale)
        kalender_nach_modus[0] = kalender_handle.nach_erscheinungsmodus_global
        kalender_ansicht_ref[0] = kalender_handle.ansicht
        haupt.bind("<Configure>", toolbox_breite_aktualisieren)

    def bei_anmeldung_ok(benutzer: Benutzer) -> None:
        aktueller_benutzer[0] = benutzer
        root.title(
            fenster_titel(
                basis_titel=get_string("app.shell.fenster_titel", locale),
                version_info=version_info,
                benutzer=benutzer.name,
                geoeffnet_um=root_geoeffnet_um,
                locale=locale,
            )
        )
        login_container.pack_forget()
        if main_content_ref[0] is None:
            shell_haupt_teil()
        mc = main_content_ref[0]
        assert mc is not None
        mc.pack(fill=tk.BOTH, expand=True)

    sensibles_leeren_ref[0] = login_ansicht_in(login_container, locale, bei_anmeldung_ok)
    login_container.pack(fill=tk.BOTH, expand=True)

    root.mainloop()
