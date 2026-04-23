"""Demo-Fenster für die Tagesansicht (Start z. B. über main.py kalender)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

from locales import get_string
from modules.arbeitszeit.einstellungen_speicher import (
    laden as arbeitseinstellungen_laden,
    speichern as arbeitseinstellungen_speichern,
)
from modules.arbeitszeit.regelprofil import RegelarbeitsProfil
from modules.fenster_info import fenster_titel, zeitstempel_jetzt
from modules.kalender import (
    KalenderAnsicht,
    KalenderIntervallBeschriftung,
    KalenderMonatRanddarstellung,
    KalenderMonatWochenstart,
    KalenderNavigationIntervall,
    KalenderNavigationsleiste,
    KalenderRasterModus,
    KalenderWocheArt,
    Tagesansicht,
    ZoomStufe,
)
from modules.kalender.farb_hilfen import hex_rgb_mit_faktor
from modules.kalender.mehrtag_kopf_einzel_tag import sprung_zu_einzel_tag
from modules.kalender.navigation_datum import (
    datum_dieser_monat_erster,
    datum_dieses_jahr_erster,
    datum_samstag_in_iso_woche_von,
)
from modules.kalender.zeitaufzeichnung_speicher import listener_entfernen, listener_registrieren
from modules.pausenzeit.profil import PausenProfil, Pausenblock, standard_arbeitspausen
from modules.theming.farben import kalender_farben
from modules.theming.modus import ist_darkmode, toggle_modus
from modules.userzeit.wachzeit import standard_wachzeit
from modules.version_info import load_version_info

_SYMBOL_EINSTELLUNGEN = "\u2699"
_SYM_RASTER_LAYOUT = "\u21C4"  # ⇄ Nebeneinander ↔ übereinander / Monat·Jahr
_INTERVALL_BUTTONS_START_PADX = (
    Tagesansicht.ZEITLEISTE_TEXT_BREITE + Tagesansicht.SONNENSPALT_BREITE + 6
)


@dataclass(frozen=True)
class KalenderDemoHandle:
    """Rückgabe-Handle für Einbettung: Zugriff auf Ansicht + Modus-Refresh."""

    ansicht: KalenderAnsicht
    nach_erscheinungsmodus_global: Callable[[], None]


def kalender_demo_in(parent: tk.Misc, locale: str = "de") -> KalenderDemoHandle:
    """Kalender-Demo in einen beliebigen Container (z. B. Shell-Mitte oder eigenes Fenster).

    Rückgabe: Callback, der nach globalem Hell/Dunkel-Wechsel (außerhalb dieses Widgets)
    Fensterhintergrund und Kalenderdarstellung nachzieht.
    """

    version_info = load_version_info()

    def fenster_hintergrund_setzen() -> None:
        bg = kalender_farben().HINTERGRUND_FENSTER
        parent.winfo_toplevel().configure(bg=bg)
        parent.configure(bg=bg)

    leiste = tk.Frame(parent)
    leiste.pack(fill=tk.X, padx=4, pady=(4, 0))

    heute = dt.date.today()
    wach = standard_wachzeit()
    standard_regelarbeit = RegelarbeitsProfil(
        wochentage=frozenset({0, 1, 3, 4, 5}),
        start_stunde=10,
        start_minute=0,
        ende_stunde=19,
        ende_minute=0,
        tageszeiten={
            0: (10, 0, 19, 0),
            1: (10, 0, 19, 0),
            3: (10, 0, 19, 0),
            4: (10, 0, 19, 0),
            5: (9, 0, 14, 0),
        },
    )
    standard_pausen = PausenProfil(
        bloecke=standard_arbeitspausen().bloecke,
        tages_bloecke={
            0: (Pausenblock.aus_start_und_dauer(14, 0, 45),),
            1: (Pausenblock.aus_start_und_dauer(14, 0, 45),),
            3: (Pausenblock.aus_start_und_dauer(14, 0, 45),),
            4: (Pausenblock.aus_start_und_dauer(14, 0, 45),),
            5: (Pausenblock.aus_start_und_dauer(11, 30, 20),),
        },
    )
    geladene_regelarbeit, geladene_pausen = arbeitseinstellungen_laden(
        standard_regelarbeit,
        standard_pausen,
    )

    regelarbeit_state: list[RegelarbeitsProfil] = [
        geladene_regelarbeit
    ]
    pausen_state: list[PausenProfil] = [
        geladene_pausen
    ]
    _mehrtag_kopf_sprung_impl: list[Callable[[dt.date], None] | None] = [None]
    _kw_woche_impl: list[Callable[[dt.date], None] | None] = [None]
    _jahr_monat_impl: list[Callable[[dt.date], None] | None] = [None]

    def _mehrtag_kopf_sprung_dispatch(tag: dt.date) -> None:
        impl = _mehrtag_kopf_sprung_impl[0]
        if impl is not None:
            impl(tag)

    def _kw_woche_dispatch(ref_datum: dt.date) -> None:
        impl = _kw_woche_impl[0]
        if impl is not None:
            impl(ref_datum)

    def _jahr_monat_dispatch(erster: dt.date) -> None:
        impl = _jahr_monat_impl[0]
        if impl is not None:
            impl(erster)

    ansicht = KalenderAnsicht(
        parent,
        heute,
        wach,
        locale=locale,
        raster_modus=KalenderRasterModus.EIN_TAG,
        start_zoom=ZoomStufe.GANZTAG,
        regelarbeit=regelarbeit_state[0],
        pausen=pausen_state[0],
        on_mehrtag_datum_einzel_tag=_mehrtag_kopf_sprung_dispatch,
        on_kw_woche=_kw_woche_dispatch,
        on_jahr_monat=_jahr_monat_dispatch,
    )

    def _kalender_nach_zeitblock() -> None:
        try:
            ansicht.darstellung_auffrischen()
        except tk.TclError:
            pass

    listener_registrieren(_kalender_nach_zeitblock)

    def _beende_zeitlistener(event: tk.Event) -> None:
        if event.widget is ansicht:
            listener_entfernen(_kalender_nach_zeitblock)

    ansicht.bind("<Destroy>", _beende_zeitlistener)

    var_raster = tk.StringVar(value="h")
    var_woche_art = tk.StringVar(value="mitte")
    var_monat_ws = tk.StringVar(value="mo")
    var_monat_rand = tk.StringVar(value="mit")
    nav_iv_holder: list[KalenderNavigationIntervall] = [
        KalenderNavigationIntervall.TAG
    ]
    _layout_extra_sync: list[Callable[[], None]] = []

    def bei_navigation(datum: dt.date) -> None:
        ansicht.datum_setzen(datum)

    def _monat_ws_enum() -> KalenderMonatWochenstart:
        return (
            KalenderMonatWochenstart.MONTAG
            if var_monat_ws.get() == "mo"
            else KalenderMonatWochenstart.SONNTAG
        )

    def _monat_rand_enum() -> KalenderMonatRanddarstellung:
        return (
            KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT
            if var_monat_rand.get() == "ohne"
            else KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
        )

    def bei_monat_layout() -> None:
        if nav_iv_holder[0] not in (
            KalenderNavigationIntervall.MONAT,
            KalenderNavigationIntervall.JAHR,
        ):
            return
        ansicht.monat_wochenstart_setzen(_monat_ws_enum())
        ansicht.monat_randdarstellung_setzen(_monat_rand_enum())

    def raster_horizontal() -> None:
        var_raster.set("h")
        iv = nav_iv_holder[0]
        if iv is KalenderNavigationIntervall.TAG:
            return
        if iv is KalenderNavigationIntervall.MONAT:
            ansicht.monat_jahr_layout_transponiert_setzen(False)
            return
        if iv is KalenderNavigationIntervall.JAHR:
            ansicht.monat_jahr_layout_transponiert_setzen(False)
            return
        if iv is KalenderNavigationIntervall.DREI_TAGE:
            ansicht.raster_modus_setzen(KalenderRasterModus.DREI_TAGE_HORIZONTAL)
        elif iv is KalenderNavigationIntervall.WOCHENENDE:
            ansicht.raster_modus_setzen(KalenderRasterModus.WOCHENENDE_HORIZONTAL)
        elif iv is KalenderNavigationIntervall.WOCHE:
            ansicht.raster_modus_setzen(KalenderRasterModus.WOCHE_HORIZONTAL)
        elif iv is KalenderNavigationIntervall.ARBEITSWOCHE:
            ansicht.raster_modus_setzen(KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL)

    def raster_vertikal() -> None:
        var_raster.set("v")
        iv = nav_iv_holder[0]
        if iv is KalenderNavigationIntervall.TAG:
            return
        if iv is KalenderNavigationIntervall.MONAT:
            ansicht.monat_jahr_layout_transponiert_setzen(True)
            return
        if iv is KalenderNavigationIntervall.JAHR:
            ansicht.monat_jahr_layout_transponiert_setzen(True)
            return
        if iv is KalenderNavigationIntervall.DREI_TAGE:
            ansicht.raster_modus_setzen(KalenderRasterModus.DREI_TAGE_VERTIKAL)
        elif iv is KalenderNavigationIntervall.WOCHENENDE:
            ansicht.raster_modus_setzen(KalenderRasterModus.WOCHENENDE_VERTIKAL)
        elif iv is KalenderNavigationIntervall.WOCHE:
            ansicht.raster_modus_setzen(KalenderRasterModus.WOCHE_VERTIKAL)
        elif iv is KalenderNavigationIntervall.ARBEITSWOCHE:
            ansicht.raster_modus_setzen(KalenderRasterModus.ARBEITSWOCHE_VERTIKAL)

    def _woche_art_aus_var() -> KalenderWocheArt:
        v = var_woche_art.get()
        if v == "mitte":
            return KalenderWocheArt.MITTE_SIEBEN_TAGE
        if v == "mo_so":
            return KalenderWocheArt.MONTAG_BIS_SONNTAG
        return KalenderWocheArt.SONNTAG_BIS_SAMSTAG

    def bei_woche_art() -> None:
        ansicht.woche_art_setzen(_woche_art_aus_var())

    def bei_intervall(iv: KalenderNavigationIntervall) -> None:
        nav_iv_holder[0] = iv
        basis_tag = ansicht.datum
        ansicht.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        if iv is KalenderNavigationIntervall.TAG:
            ansicht.raster_modus_setzen(KalenderRasterModus.EIN_TAG)
        elif iv is KalenderNavigationIntervall.DREI_TAGE:
            if var_raster.get() == "h":
                ansicht.raster_modus_setzen(KalenderRasterModus.DREI_TAGE_HORIZONTAL)
            else:
                ansicht.raster_modus_setzen(KalenderRasterModus.DREI_TAGE_VERTIKAL)
            bei_navigation(basis_tag)
        elif iv is KalenderNavigationIntervall.WOCHENENDE:
            if var_raster.get() == "h":
                ansicht.raster_modus_setzen(KalenderRasterModus.WOCHENENDE_HORIZONTAL)
            else:
                ansicht.raster_modus_setzen(KalenderRasterModus.WOCHENENDE_VERTIKAL)
            bei_navigation(datum_samstag_in_iso_woche_von(basis_tag))
        elif iv is KalenderNavigationIntervall.WOCHE:
            ansicht.woche_art_setzen(_woche_art_aus_var())
            if var_raster.get() == "h":
                ansicht.raster_modus_setzen(KalenderRasterModus.WOCHE_HORIZONTAL)
            else:
                ansicht.raster_modus_setzen(KalenderRasterModus.WOCHE_VERTIKAL)
            bei_navigation(basis_tag)
        elif iv is KalenderNavigationIntervall.ARBEITSWOCHE:
            if var_raster.get() == "h":
                ansicht.raster_modus_setzen(KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL)
            else:
                ansicht.raster_modus_setzen(KalenderRasterModus.ARBEITSWOCHE_VERTIKAL)
            bei_navigation(basis_tag)
        elif iv is KalenderNavigationIntervall.MONAT:
            ansicht.monat_jahr_layout_transponiert_setzen(var_raster.get() == "v")
            ansicht.monat_wochenstart_setzen(_monat_ws_enum())
            ansicht.monat_randdarstellung_setzen(_monat_rand_enum())
            ansicht.raster_modus_setzen(KalenderRasterModus.MONAT)
            bei_navigation(datum_dieser_monat_erster())
        elif iv is KalenderNavigationIntervall.JAHR:
            ansicht.monat_jahr_layout_transponiert_setzen(var_raster.get() == "v")
            ansicht.monat_wochenstart_setzen(_monat_ws_enum())
            ansicht.monat_randdarstellung_setzen(_monat_rand_enum())
            ansicht.raster_modus_setzen(KalenderRasterModus.JAHR)
            bei_navigation(datum_dieses_jahr_erster())
        for fn in _layout_extra_sync:
            fn()

    nav_leiste = KalenderNavigationsleiste(
        parent,
        locale=locale,
        on_datum=bei_navigation,
        on_intervall=bei_intervall,
        intervall_beschriftung=KalenderIntervallBeschriftung.WORT,
        intervall_start_padx=_INTERVALL_BUTTONS_START_PADX,
        aktueller_tag_fn=lambda: ansicht.datum,
    )

    def _mehrtag_kopf_nach_einzel_tag(tag: dt.date) -> None:
        sprung_zu_einzel_tag(
            tag,
            zeitraum_auf_tag_stellen=lambda: nav_leiste.intervall_programm_setzen(
                KalenderNavigationIntervall.TAG
            ),
            kalendertag_anzeigen=bei_navigation,
        )

    _mehrtag_kopf_sprung_impl[0] = _mehrtag_kopf_nach_einzel_tag

    def _von_kw_zur_woche(ref_datum: dt.date) -> None:
        nav_leiste.intervall_programm_setzen(KalenderNavigationIntervall.WOCHE)
        bei_navigation(ref_datum)

    _kw_woche_impl[0] = _von_kw_zur_woche

    def _von_jahr_zu_monat(erster: dt.date) -> None:
        nav_leiste.intervall_programm_setzen(KalenderNavigationIntervall.MONAT)
        bei_navigation(erster)

    _jahr_monat_impl[0] = _von_jahr_zu_monat
    re = nav_leiste.rechts_neben_nav_buttons

    class _LeistenToolTip:
        def __init__(self, widget: tk.Misc, text: str) -> None:
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
            kft = kalender_farben()
            f = tk.Frame(self._tip, bg=kft.TEXT_ZEIT, bd=1, highlightthickness=0)
            f.pack()
            tk.Label(
                f,
                text=self._text,
                bg=kft.TEXT_ZEIT,
                fg=kft.HINTERGRUND_BLATT,
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

    def _taste_grundstil(
        taste: tk.Button,
        *,
        basis_bg: str,
        aktiv: bool = False,
    ) -> None:
        normal = basis_bg
        aktiv_bg = hex_rgb_mit_faktor(basis_bg, 0.88)
        ziel = aktiv_bg if aktiv else normal
        taste.configure(
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=ziel,
            fg=kalender_farben().TEXT_ZEIT,
            activebackground=ziel,
            activeforeground=kalender_farben().TEXT_ZEIT,
        )

    def _taste_hover_binden(
        taste: tk.Button,
        *,
        basis_bg: str,
        ist_aktiv: Callable[[], bool] | None = None,
    ) -> None:
        hover = hex_rgb_mit_faktor(basis_bg, 0.93)
        aktiv_bg = hex_rgb_mit_faktor(basis_bg, 0.88)
        aktiv_hover = hex_rgb_mit_faktor(basis_bg, 0.84)

        def _ein(_event: tk.Event | None = None) -> None:
            aktiv = ist_aktiv() if ist_aktiv is not None else False
            taste.configure(bg=aktiv_hover if aktiv else hover)

        def _aus(_event: tk.Event | None = None) -> None:
            aktiv = ist_aktiv() if ist_aktiv is not None else False
            taste.configure(bg=aktiv_bg if aktiv else basis_bg)

        taste.bind("<Enter>", _ein)
        taste.bind("<Leave>", _aus)

    def _toggle_sync(
        buttons: dict[str, tk.Button],
        aktiv: str,
        *,
        basis_bg: str,
    ) -> None:
        for key, btn in buttons.items():
            _taste_grundstil(btn, basis_bg=basis_bg, aktiv=(key == aktiv))

    kf_nav = kalender_farben()
    btn_raster_layout = tk.Button(
        re,
        text=_SYM_RASTER_LAYOUT,
        font=("Segoe UI", 12),
        width=2,
        height=1,
    )
    _taste_grundstil(btn_raster_layout, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(btn_raster_layout, basis_bg=kf_nav.HINTERGRUND_FENSTER)

    def _raster_layout_icon_klick() -> None:
        if var_raster.get() == "h":
            raster_vertikal()
        else:
            raster_horizontal()

    btn_raster_layout.configure(command=_raster_layout_icon_klick)
    _LeistenToolTip(
        btn_raster_layout,
        get_string("kalender.raster_layout_icon_tooltip", locale),
    )

    monat_rahmen = tk.Frame(re)
    monat_ws_buttons: dict[str, tk.Button] = {}
    monat_rand_buttons: dict[str, tk.Button] = {}

    def _monat_ws_setzen(wert: str) -> Callable[[], None]:
        def _ruf() -> None:
            var_monat_ws.set(wert)
            _toggle_sync(
                monat_ws_buttons,
                var_monat_ws.get(),
                basis_bg=kf_nav.HINTERGRUND_FENSTER,
            )
            bei_monat_layout()

        return _ruf

    b_monat_mo = tk.Button(
        monat_rahmen,
        text=get_string("kalender.monat_layout_mo_so", locale),
        command=_monat_ws_setzen("mo"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_monat_mo, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_monat_mo,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_monat_ws.get() == "mo",
    )
    b_monat_mo.pack(side=tk.LEFT, padx=(4, 0))
    monat_ws_buttons["mo"] = b_monat_mo
    b_monat_so = tk.Button(
        monat_rahmen,
        text=get_string("kalender.monat_layout_so_sa", locale),
        command=_monat_ws_setzen("so"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_monat_so, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_monat_so,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_monat_ws.get() == "so",
    )
    b_monat_so.pack(side=tk.LEFT, padx=(4, 0))
    monat_ws_buttons["so"] = b_monat_so

    def _monat_rand_setzen(wert: str) -> Callable[[], None]:
        def _ruf() -> None:
            var_monat_rand.set(wert)
            _toggle_sync(
                monat_rand_buttons,
                var_monat_rand.get(),
                basis_bg=kf_nav.HINTERGRUND_FENSTER,
            )
            bei_monat_layout()

        return _ruf

    b_rand_ohne = tk.Button(
        monat_rahmen,
        text=get_string("kalender.monat_rand_nur", locale),
        command=_monat_rand_setzen("ohne"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_rand_ohne, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_rand_ohne,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_monat_rand.get() == "ohne",
    )
    b_rand_ohne.pack(side=tk.LEFT, padx=(4, 0))
    monat_rand_buttons["ohne"] = b_rand_ohne
    b_rand_mit = tk.Button(
        monat_rahmen,
        text=get_string("kalender.monat_rand_mit", locale),
        command=_monat_rand_setzen("mit"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_rand_mit, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_rand_mit,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_monat_rand.get() == "mit",
    )
    b_rand_mit.pack(side=tk.LEFT, padx=(4, 0))
    monat_rand_buttons["mit"] = b_rand_mit
    _toggle_sync(
        monat_ws_buttons,
        var_monat_ws.get(),
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
    )
    _toggle_sync(
        monat_rand_buttons,
        var_monat_rand.get(),
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
    )

    week_rahmen = tk.Frame(re)
    woche_art_buttons: dict[str, tk.Button] = {}

    def _woche_art_setzen(wert: str) -> Callable[[], None]:
        def _ruf() -> None:
            var_woche_art.set(wert)
            _toggle_sync(
                woche_art_buttons,
                var_woche_art.get(),
                basis_bg=kf_nav.HINTERGRUND_FENSTER,
            )
            bei_woche_art()

        return _ruf

    b_woche_mitte = tk.Button(
        week_rahmen,
        text=get_string("kalender.woche_art_mitte", locale),
        command=_woche_art_setzen("mitte"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_woche_mitte, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_woche_mitte,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_woche_art.get() == "mitte",
    )
    b_woche_mitte.pack(side=tk.LEFT, padx=(4, 0))
    woche_art_buttons["mitte"] = b_woche_mitte
    b_woche_mo_so = tk.Button(
        week_rahmen,
        text=get_string("kalender.woche_art_mo_so", locale),
        command=_woche_art_setzen("mo_so"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_woche_mo_so, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_woche_mo_so,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_woche_art.get() == "mo_so",
    )
    b_woche_mo_so.pack(side=tk.LEFT, padx=(4, 0))
    woche_art_buttons["mo_so"] = b_woche_mo_so
    b_woche_so_sa = tk.Button(
        week_rahmen,
        text=get_string("kalender.woche_art_so_sa", locale),
        command=_woche_art_setzen("so_sa"),
        padx=6,
        pady=1,
    )
    _taste_grundstil(b_woche_so_sa, basis_bg=kf_nav.HINTERGRUND_FENSTER)
    _taste_hover_binden(
        b_woche_so_sa,
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
        ist_aktiv=lambda: var_woche_art.get() == "so_sa",
    )
    b_woche_so_sa.pack(side=tk.LEFT, padx=(4, 0))
    woche_art_buttons["so_sa"] = b_woche_so_sa
    _toggle_sync(
        woche_art_buttons,
        var_woche_art.get(),
        basis_bg=kf_nav.HINTERGRUND_FENSTER,
    )

    def layout_raster_extra_sync() -> None:
        iv = nav_iv_holder[0]
        if iv is KalenderNavigationIntervall.TAG:
            nav_leiste.raster_layout_steuerung_ausblenden()
            return
        nav_leiste.raster_layout_steuerung_einblenden()
        if iv in (
            KalenderNavigationIntervall.MONAT,
            KalenderNavigationIntervall.JAHR,
        ):
            week_rahmen.pack_forget()
            btn_raster_layout.pack(side=tk.LEFT, padx=(_INTERVALL_BUTTONS_START_PADX, 0))
            monat_rahmen.pack(side=tk.LEFT, padx=(8, 0))
            return
        monat_rahmen.pack_forget()
        btn_raster_layout.pack(side=tk.LEFT, padx=(_INTERVALL_BUTTONS_START_PADX, 0))
        if iv is KalenderNavigationIntervall.WOCHE:
            week_rahmen.pack(side=tk.LEFT, padx=(8, 0))
        else:
            week_rahmen.pack_forget()

    _layout_extra_sync.append(layout_raster_extra_sync)

    nav_leiste.pack(fill=tk.X, padx=4, pady=(2, 0))

    ansicht.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
    layout_raster_extra_sync()

    def _zeit_als_text(stunde: int, minute: int) -> str:
        return f"{stunde:02d}:{minute:02d}"

    def _zeit_parsen(text: str) -> tuple[int, int]:
        roh = text.strip()
        teile = roh.split(":")
        if len(teile) != 2:
            raise ValueError(roh)
        stunde = int(teile[0])
        minute = int(teile[1])
        if not (0 <= stunde <= 23 and 0 <= minute <= 59):
            raise ValueError(roh)
        return (stunde, minute)

    def _arbeitszeit_fuer_wochentag(wochentag: int) -> tuple[int, int]:
        profil = regelarbeit_state[0]
        if profil.tageszeiten is not None and wochentag in profil.tageszeiten:
            sh, sm, eh, em = profil.tageszeiten[wochentag]
            return (sh * 60 + sm, eh * 60 + em)
        return (
            profil.start_stunde * 60 + profil.start_minute,
            profil.ende_stunde * 60 + profil.ende_minute,
        )

    def _pause_fuer_wochentag(wochentag: int) -> Pausenblock | None:
        p = pausen_state[0]
        if p.tages_bloecke is not None and wochentag in p.tages_bloecke:
            blocks = p.tages_bloecke[wochentag]
            return blocks[0] if blocks else None
        if p.bloecke:
            return p.bloecke[0]
        return None

    def bei_einstellungen() -> None:
        win = tk.Toplevel(parent.winfo_toplevel())
        win.title(
            fenster_titel(
                basis_titel=get_string("kalender.einstellungen_fenster_titel", locale),
                version_info=version_info,
                benutzer="Gast",
                geoeffnet_um=zeitstempel_jetzt(),
                locale=locale,
            )
        )
        win.configure(bg=kalender_farben().HINTERGRUND_FENSTER)
        win.geometry("980x720")
        rahmen = tk.Frame(win, bg=kalender_farben().HINTERGRUND_FENSTER)
        rahmen.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tk.Label(
            rahmen,
            text=get_string("kalender.einstellungen_arbeit_bereich", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(0, 8))

        inhalt_rahmen = tk.Frame(rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        inhalt_rahmen.pack(fill=tk.X)
        tabellen_rahmen = tk.Frame(inhalt_rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        tabellen_rahmen.pack(side=tk.LEFT, fill=tk.X, expand=True)
        summen_rahmen = tk.Frame(inhalt_rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        summen_rahmen.pack(side=tk.RIGHT, anchor=tk.NE, padx=(16, 0))

        tk.Label(
            tabellen_rahmen,
            text="",
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        tage_kurz = [get_string(f"kalender.wochentag_kurz.{i}", locale) for i in range(7)]
        ausgewaehlte_wochentage: set[int] = set(regelarbeit_state[0].wochentage)
        zeiten_rahmen = tk.Frame(tabellen_rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        zeiten_rahmen.pack(anchor=tk.W)
        wochentag_buttons: dict[int, tk.Button] = {}
        arbeits_start_entries: dict[int, tk.Entry] = {}
        arbeits_ende_entries: dict[int, tk.Entry] = {}
        arbeitszeit_cache: dict[int, tuple[str, str]] = {}
        pause_cache: dict[int, tuple[str, str, str]] = {}
        for i in range(7):
            start_m, ende_m = _arbeitszeit_fuer_wochentag(i)
            sh, sm = divmod(start_m, 60)
            eh, em = divmod(ende_m, 60)
            arbeitszeit_cache[i] = (_zeit_als_text(sh, sm), _zeit_als_text(eh, em))
            pb = _pause_fuer_wochentag(i)
            if pb is None:
                pause_cache[i] = ("", "", "")
            else:
                pause_cache[i] = (
                    _zeit_als_text(pb.start_stunde, pb.start_minute),
                    str(max(1, pb.dauer_minuten)),
                    _zeit_als_text(pb.ende_stunde, pb.ende_minute),
                )

        tk.Label(
            zeiten_rahmen,
            text=get_string("kalender.einstellungen_arbeitstage_label", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
            width=18,
        ).grid(row=0, column=0, sticky="w")
        for i, tag in enumerate(tage_kurz):
            btn = tk.Button(
                zeiten_rahmen,
                text=tag,
                padx=6,
                pady=2,
                width=6,
            )
            btn.grid(row=0, column=i + 1, padx=(0, 4), pady=(0, 4))
            wochentag_buttons[i] = btn

        tk.Label(
            zeiten_rahmen,
            text=get_string("kalender.einstellungen_arbeitszeit_anfang_zeile", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
            width=18,
        ).grid(row=1, column=0, sticky="w")
        tk.Label(
            zeiten_rahmen,
            text=get_string("kalender.einstellungen_arbeitszeit_ende_zeile", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
            width=18,
        ).grid(row=2, column=0, sticky="w")

        for i in range(7):
            start_entry = tk.Entry(zeiten_rahmen, width=7, justify=tk.CENTER)
            ende_entry = tk.Entry(zeiten_rahmen, width=7, justify=tk.CENTER)
            start_entry.grid(row=1, column=i + 1, padx=(0, 4), pady=(0, 4))
            ende_entry.grid(row=2, column=i + 1, padx=(0, 4), pady=(0, 4))
            arbeits_start_entries[i] = start_entry
            arbeits_ende_entries[i] = ende_entry

        tk.Label(
            tabellen_rahmen,
            text=get_string("kalender.einstellungen_pausen_bereich", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
            justify=tk.LEFT,
        ).pack(fill=tk.X, pady=(16, 8))

        pausen_rahmen = tk.Frame(tabellen_rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        pausen_rahmen.pack(anchor=tk.W)
        pause_start_entries: dict[int, tk.Entry] = {}
        pause_dauer_entries: dict[int, tk.Entry] = {}
        pause_ende_entries: dict[int, tk.Entry] = {}

        tk.Label(
            pausen_rahmen,
            text="",
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            width=18,
            anchor=tk.W,
        ).grid(row=0, column=0, sticky="w")
        for i, tag in enumerate(tage_kurz):
            tk.Button(
                pausen_rahmen,
                text=tag,
                command=lambda w=i: wochentag_buttons[w].invoke(),
                padx=6,
                pady=2,
                width=6,
                bg=kalender_farben().HINTERGRUND_FENSTER,
                fg=kalender_farben().TEXT_ZEIT,
                activebackground=kalender_farben().HINTERGRUND_FENSTER,
                activeforeground=kalender_farben().TEXT_ZEIT,
                relief=tk.FLAT,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            ).grid(row=0, column=i + 1, padx=(0, 4), pady=(0, 4))

        tk.Label(
            pausen_rahmen,
            text=get_string("kalender.einstellungen_pause_anfang_zeile", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            width=18,
            anchor=tk.W,
        ).grid(row=1, column=0, sticky="w")
        tk.Label(
            pausen_rahmen,
            text=get_string("kalender.einstellungen_pause_dauer_zeile", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            width=18,
            anchor=tk.W,
        ).grid(row=2, column=0, sticky="w")
        tk.Label(
            pausen_rahmen,
            text=get_string("kalender.einstellungen_pause_ende_zeile", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            width=18,
            anchor=tk.W,
        ).grid(row=3, column=0, sticky="w")

        wochenarbeit_var = tk.StringVar(value="00:00")
        wochenpause_var = tk.StringVar(value="00:00")
        tk.Label(
            summen_rahmen,
            text=get_string("kalender.einstellungen_wochenzeit_bereich", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(0, 8))
        tk.Label(
            summen_rahmen,
            text=get_string("kalender.einstellungen_wochenarbeitszeit", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
        ).pack(anchor=tk.W)
        tk.Label(
            summen_rahmen,
            textvariable=wochenarbeit_var,
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
        ).pack(anchor=tk.W, pady=(0, 8))
        tk.Label(
            summen_rahmen,
            text=get_string("kalender.einstellungen_wochenpausenzeit", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            anchor=tk.W,
        ).pack(anchor=tk.W)
        tk.Label(
            summen_rahmen,
            textvariable=wochenpause_var,
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
        ).pack(anchor=tk.W)

        def _dauer_format(minuten: int) -> str:
            st, mi = divmod(max(0, minuten), 60)
            return f"{st:02d}:{mi:02d}"

        def _entry_text_setzen(entry: tk.Entry, text: str) -> None:
            state = str(entry.cget("state"))
            if state == tk.DISABLED:
                entry.configure(state=tk.NORMAL)
                entry.delete(0, tk.END)
                entry.insert(0, text)
                entry.configure(state=tk.DISABLED)
                return
            entry.delete(0, tk.END)
            entry.insert(0, text)

        def _cache_aktualisieren_aus_feldern() -> None:
            for i in range(7):
                if str(arbeits_start_entries[i].cget("state")) != tk.DISABLED:
                    arbeitszeit_cache[i] = (
                        arbeits_start_entries[i].get().strip(),
                        arbeits_ende_entries[i].get().strip(),
                    )
                if str(pause_start_entries[i].cget("state")) != tk.DISABLED:
                    pause_cache[i] = (
                        pause_start_entries[i].get().strip(),
                        pause_dauer_entries[i].get().strip(),
                        pause_ende_entries[i].get().strip(),
                    )

        def _arbeitszeit_felder_sync() -> None:
            for i in range(7):
                aktiv = i in ausgewaehlte_wochentage
                if aktiv:
                    if not arbeits_start_entries[i].get().strip():
                        _entry_text_setzen(arbeits_start_entries[i], arbeitszeit_cache[i][0])
                    if not arbeits_ende_entries[i].get().strip():
                        _entry_text_setzen(arbeits_ende_entries[i], arbeitszeit_cache[i][1])
                    arbeits_start_entries[i].configure(state=tk.NORMAL)
                    arbeits_ende_entries[i].configure(state=tk.NORMAL)
                else:
                    arbeitszeit_cache[i] = (
                        arbeits_start_entries[i].get().strip(),
                        arbeits_ende_entries[i].get().strip(),
                    )
                    _entry_text_setzen(arbeits_start_entries[i], "")
                    _entry_text_setzen(arbeits_ende_entries[i], "")
                    arbeits_start_entries[i].configure(state=tk.DISABLED)
                    arbeits_ende_entries[i].configure(state=tk.DISABLED)

        def _pausen_felder_sync() -> None:
            for i in range(7):
                aktiv = i in ausgewaehlte_wochentage
                if aktiv:
                    ps, pd, pe = pause_cache[i]
                    if not pause_start_entries[i].get().strip():
                        _entry_text_setzen(pause_start_entries[i], ps)
                    if not pause_dauer_entries[i].get().strip():
                        _entry_text_setzen(pause_dauer_entries[i], pd)
                    if not pause_ende_entries[i].get().strip():
                        _entry_text_setzen(pause_ende_entries[i], pe)
                    pause_start_entries[i].configure(state=tk.NORMAL)
                    pause_dauer_entries[i].configure(state=tk.NORMAL)
                    pause_ende_entries[i].configure(state=tk.NORMAL)
                else:
                    pause_cache[i] = (
                        pause_start_entries[i].get().strip(),
                        pause_dauer_entries[i].get().strip(),
                        pause_ende_entries[i].get().strip(),
                    )
                    _entry_text_setzen(pause_start_entries[i], "")
                    _entry_text_setzen(pause_dauer_entries[i], "")
                    _entry_text_setzen(pause_ende_entries[i], "")
                    pause_start_entries[i].configure(state=tk.DISABLED)
                    pause_dauer_entries[i].configure(state=tk.DISABLED)
                    pause_ende_entries[i].configure(state=tk.DISABLED)

        def _pausen_zeile_rechnen(tag_index: int, quelle: str) -> None:
            if tag_index not in ausgewaehlte_wochentage:
                return
            start_text = pause_start_entries[tag_index].get().strip()
            dauer_text = pause_dauer_entries[tag_index].get().strip()
            ende_text = pause_ende_entries[tag_index].get().strip()
            if not start_text:
                return
            try:
                sh, sm = _zeit_parsen(start_text)
            except ValueError:
                return
            if quelle in ("dauer", "start") and dauer_text:
                try:
                    dauer = int(dauer_text)
                    if dauer <= 0:
                        return
                    block = Pausenblock.aus_start_und_dauer(sh, sm, dauer)
                except (ValueError, TypeError):
                    return
                _entry_text_setzen(
                    pause_ende_entries[tag_index],
                    _zeit_als_text(block.ende_stunde, block.ende_minute),
                )
                return
            if quelle in ("ende", "start") and ende_text:
                try:
                    eh, em = _zeit_parsen(ende_text)
                except ValueError:
                    return
                dauer = eh * 60 + em - (sh * 60 + sm)
                if dauer <= 0:
                    return
                _entry_text_setzen(pause_dauer_entries[tag_index], str(dauer))

        def _wochen_summen_aktualisieren() -> None:
            arbeit_summe = 0
            pause_summe = 0
            for i in sorted(ausgewaehlte_wochentage):
                tag_arbeit = 0
                try:
                    sh, sm = _zeit_parsen(arbeits_start_entries[i].get().strip())
                    eh, em = _zeit_parsen(arbeits_ende_entries[i].get().strip())
                    diff = eh * 60 + em - (sh * 60 + sm)
                    if diff > 0:
                        tag_arbeit = diff
                except ValueError:
                    pass
                tag_pause = 0
                start_text = pause_start_entries[i].get().strip()
                dauer_text = pause_dauer_entries[i].get().strip()
                ende_text = pause_ende_entries[i].get().strip()
                try:
                    if start_text and dauer_text:
                        dauer = int(dauer_text)
                        if dauer > 0:
                            tag_pause = dauer
                    elif start_text and ende_text:
                        sh, sm = _zeit_parsen(start_text)
                        eh, em = _zeit_parsen(ende_text)
                        diff = eh * 60 + em - (sh * 60 + sm)
                        if diff > 0:
                            tag_pause = diff
                except (ValueError, TypeError):
                    pass
                pause_summe += tag_pause
                arbeit_summe += max(0, tag_arbeit - tag_pause)
            wochenarbeit_var.set(_dauer_format(arbeit_summe))
            wochenpause_var.set(_dauer_format(pause_summe))

        def _wochentag_button_sync() -> None:
            for i, btn in wochentag_buttons.items():
                _taste_grundstil(
                    btn,
                    basis_bg=kalender_farben().HINTERGRUND_FENSTER,
                    aktiv=(i in ausgewaehlte_wochentage),
                )
                _taste_hover_binden(
                    btn,
                    basis_bg=kalender_farben().HINTERGRUND_FENSTER,
                    ist_aktiv=lambda w=i: w in ausgewaehlte_wochentage,
                )

        def _wochentag_toggle(tag_index: int) -> Callable[[], None]:
            def _ruf() -> None:
                _cache_aktualisieren_aus_feldern()
                if tag_index in ausgewaehlte_wochentage:
                    ausgewaehlte_wochentage.remove(tag_index)
                else:
                    ausgewaehlte_wochentage.add(tag_index)
                _wochentag_button_sync()
                _arbeitszeit_felder_sync()
                _pausen_felder_sync()
                _wochen_summen_aktualisieren()

            return _ruf

        for i in range(7):
            start_entry = tk.Entry(pausen_rahmen, width=7, justify=tk.CENTER)
            dauer_entry = tk.Entry(pausen_rahmen, width=7, justify=tk.CENTER)
            ende_entry = tk.Entry(
                pausen_rahmen,
                width=7,
                justify=tk.CENTER,
            )
            start_entry.grid(row=1, column=i + 1, padx=(0, 4), pady=(0, 4))
            dauer_entry.grid(row=2, column=i + 1, padx=(0, 4), pady=(0, 4))
            ende_entry.grid(row=3, column=i + 1, padx=(0, 4))
            ps, pd, pe = pause_cache[i]
            start_entry.insert(0, ps)
            dauer_entry.insert(0, pd)
            ende_entry.insert(0, pe)
            pause_start_entries[i] = start_entry
            pause_dauer_entries[i] = dauer_entry
            pause_ende_entries[i] = ende_entry

        for i in range(7):
            wochentag_buttons[i].configure(command=_wochentag_toggle(i))
            arbeits_start_entries[i].bind("<KeyRelease>", lambda _e, w=i: _wochen_summen_aktualisieren())
            arbeits_ende_entries[i].bind("<KeyRelease>", lambda _e, w=i: _wochen_summen_aktualisieren())
            pause_start_entries[i].bind(
                "<KeyRelease>",
                lambda _e, w=i: (
                    _pausen_zeile_rechnen(w, "start"),
                    _wochen_summen_aktualisieren(),
                ),
            )
            pause_dauer_entries[i].bind(
                "<KeyRelease>",
                lambda _e, w=i: (
                    _pausen_zeile_rechnen(w, "dauer"),
                    _wochen_summen_aktualisieren(),
                ),
            )
            pause_ende_entries[i].bind(
                "<KeyRelease>",
                lambda _e, w=i: (
                    _pausen_zeile_rechnen(w, "ende"),
                    _wochen_summen_aktualisieren(),
                ),
            )

        _wochentag_button_sync()
        _arbeitszeit_felder_sync()
        _pausen_felder_sync()
        _wochen_summen_aktualisieren()

        beschriftung_rahmen = tk.Frame(tabellen_rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        beschriftung_rahmen.pack(fill=tk.X, pady=(18, 0))
        tk.Label(
            beschriftung_rahmen,
            text=get_string("kalender.nav_design_label", locale),
            bg=kalender_farben().HINTERGRUND_FENSTER,
            fg=kalender_farben().TEXT_ZEIT,
        ).pack(anchor=tk.W)

        var_nav_design = tk.StringVar(value=nav_leiste.intervall_beschriftung().name)

        def _beschriftung_auswahl() -> None:
            try:
                stil = KalenderIntervallBeschriftung[var_nav_design.get()]
            except KeyError:
                stil = KalenderIntervallBeschriftung.WORT
            nav_leiste.intervall_beschriftung_setzen(stil)

        optionen = [
            ("kalender.nav_design.wort", KalenderIntervallBeschriftung.WORT),
            ("kalender.nav_design.kuerzel_de", KalenderIntervallBeschriftung.KUERZEL_DE),
            ("kalender.nav_design.icon", KalenderIntervallBeschriftung.ICON),
        ]
        nav_design_buttons: dict[str, tk.Button] = {}

        def _nav_design_setzen(stil: KalenderIntervallBeschriftung) -> Callable[[], None]:
            def _ruf() -> None:
                var_nav_design.set(stil.name)
                _toggle_sync(
                    nav_design_buttons,
                    var_nav_design.get(),
                    basis_bg=kalender_farben().HINTERGRUND_FENSTER,
                )
                _beschriftung_auswahl()

            return _ruf

        for schluessel, stil in optionen:
            b = tk.Button(
                beschriftung_rahmen,
                text=get_string(schluessel, locale),
                command=_nav_design_setzen(stil),
                padx=6,
                pady=2,
            )
            _taste_grundstil(b, basis_bg=kalender_farben().HINTERGRUND_FENSTER)
            _taste_hover_binden(
                b,
                basis_bg=kalender_farben().HINTERGRUND_FENSTER,
                ist_aktiv=lambda s=stil: var_nav_design.get() == s.name,
            )
            b.pack(anchor=tk.W, padx=(8, 0), pady=(4, 0))
            nav_design_buttons[stil.name] = b
        _toggle_sync(
            nav_design_buttons,
            var_nav_design.get(),
            basis_bg=kalender_farben().HINTERGRUND_FENSTER,
        )

        knopf_rahmen = tk.Frame(rahmen, bg=kalender_farben().HINTERGRUND_FENSTER)
        knopf_rahmen.pack(fill=tk.X, pady=(20, 0))

        def _arbeit_und_pausen_speichern() -> None:
            if not ausgewaehlte_wochentage:
                messagebox.showerror(
                    get_string("kalender.einstellungen_fehler_titel", locale),
                    get_string("kalender.einstellungen_fehler_wochentage", locale),
                    parent=win,
                )
                return
            tageszeiten: dict[int, tuple[int, int, int, int]] = {}
            pause_tagesbloecke: dict[int, tuple[Pausenblock, ...]] = {}
            for i in sorted(ausgewaehlte_wochentage):
                tag_name = get_string(f"kalender.wochentag_lang.{i}", locale)
                try:
                    sh, sm = _zeit_parsen(arbeits_start_entries[i].get())
                    eh, em = _zeit_parsen(arbeits_ende_entries[i].get())
                except ValueError:
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_arbeitszeit_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                tag_start = sh * 60 + sm
                tag_ende = eh * 60 + em
                if tag_start >= tag_ende:
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_arbeitszeit_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                tageszeiten[i] = (sh, sm, eh, em)

                pause_start_text = pause_start_entries[i].get().strip()
                pause_dauer_text = pause_dauer_entries[i].get().strip()
                pause_ende_text = pause_ende_entries[i].get().strip()
                if not pause_start_text and not pause_dauer_text and not pause_ende_text:
                    continue
                if not pause_start_text:
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_pause_unvollstaendig_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                if not pause_dauer_text and not pause_ende_text:
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_pause_unvollstaendig_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                try:
                    psh, psm = _zeit_parsen(pause_start_text)
                except ValueError:
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_pause_dauer_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                block: Pausenblock | None = None
                if pause_dauer_text:
                    try:
                        dauer = int(pause_dauer_text)
                        block = Pausenblock.aus_start_und_dauer(psh, psm, dauer)
                    except (ValueError, TypeError):
                        messagebox.showerror(
                            get_string("kalender.einstellungen_fehler_titel", locale),
                            get_string("kalender.einstellungen_fehler_pause_dauer_tag", locale).format(
                                tag=tag_name
                            ),
                            parent=win,
                        )
                        return
                    if pause_ende_text:
                        try:
                            eh, em = _zeit_parsen(pause_ende_text)
                        except ValueError:
                            messagebox.showerror(
                                get_string("kalender.einstellungen_fehler_titel", locale),
                                get_string("kalender.einstellungen_fehler_pause_ende_tag", locale).format(
                                    tag=tag_name
                                ),
                                parent=win,
                            )
                            return
                        if (eh, em) != (block.ende_stunde, block.ende_minute):
                            messagebox.showerror(
                                get_string("kalender.einstellungen_fehler_titel", locale),
                                get_string("kalender.einstellungen_fehler_pause_konflikt_tag", locale).format(
                                    tag=tag_name
                                ),
                                parent=win,
                            )
                            return
                else:
                    try:
                        eh, em = _zeit_parsen(pause_ende_text)
                    except ValueError:
                        messagebox.showerror(
                            get_string("kalender.einstellungen_fehler_titel", locale),
                            get_string("kalender.einstellungen_fehler_pause_ende_tag", locale).format(
                                tag=tag_name
                            ),
                            parent=win,
                        )
                        return
                    dauer = eh * 60 + em - (psh * 60 + psm)
                    if dauer <= 0:
                        messagebox.showerror(
                            get_string("kalender.einstellungen_fehler_titel", locale),
                            get_string("kalender.einstellungen_fehler_pause_ende_tag", locale).format(
                                tag=tag_name
                            ),
                            parent=win,
                        )
                        return
                    block = Pausenblock.aus_start_und_dauer(psh, psm, dauer)
                if (
                    block.start_minuten_seit_mitternacht < tag_start
                    or block.ende_minuten_seit_mitternacht > tag_ende
                ):
                    messagebox.showerror(
                        get_string("kalender.einstellungen_fehler_titel", locale),
                        get_string("kalender.einstellungen_fehler_pause_arbeitsrahmen_tag", locale).format(
                            tag=tag_name
                        ),
                        parent=win,
                    )
                    return
                pause_tagesbloecke[i] = (block,)

            erster_tag = min(tageszeiten)
            start_h, start_m, ende_h, ende_m = tageszeiten[erster_tag]

            alte_regel = regelarbeit_state[0]
            neue_regel = RegelarbeitsProfil(
                wochentage=frozenset(ausgewaehlte_wochentage),
                start_stunde=start_h,
                start_minute=start_m,
                ende_stunde=ende_h,
                ende_minute=ende_m,
                tageszeiten=tageszeiten,
                farbe_arbeit_hex=alte_regel.farbe_arbeit_hex,
            )
            alte_pausen = pausen_state[0]
            neue_pausen = PausenProfil(
                bloecke=tuple(v[0] for v in pause_tagesbloecke.values())
                if pause_tagesbloecke
                else tuple(),
                tages_bloecke=pause_tagesbloecke,
                farbe_pause_hex=alte_pausen.farbe_pause_hex,
            )

            regelarbeit_state[0] = neue_regel
            pausen_state[0] = neue_pausen
            arbeitseinstellungen_speichern(neue_regel, neue_pausen)
            ansicht.regelarbeit_setzen(neue_regel)
            ansicht.pausen_setzen(neue_pausen)
            ansicht.darstellung_auffrischen()
            win.destroy()

        tk.Button(
            knopf_rahmen,
            text=get_string("kalender.einstellungen_speichern", locale),
            command=_arbeit_und_pausen_speichern,
            padx=12,
            pady=4,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=kalender_farben().HINTERGRUND_ZEITLEISTE,
            fg=kalender_farben().TEXT_ZEIT,
            activebackground=kalender_farben().RASTER_STUNDE,
            activeforeground=kalender_farben().TEXT_ZEIT,
        ).pack(side=tk.RIGHT)

    _icon_font = tkfont.Font(parent.winfo_toplevel(), family="Segoe UI", size=14)

    kf0 = kalender_farben()
    btn_kwargs: dict[str, object] = {"font": _icon_font, "width": 3}

    einstellungen_btn = tk.Button(
        leiste,
        text=_SYMBOL_EINSTELLUNGEN,
        command=bei_einstellungen,
        **btn_kwargs,
    )
    _taste_grundstil(einstellungen_btn, basis_bg=kf0.HINTERGRUND_FENSTER)
    _taste_hover_binden(einstellungen_btn, basis_bg=kf0.HINTERGRUND_FENSTER)
    einstellungen_btn.pack(side=tk.RIGHT, padx=(0, 2))

    pause_btn = tk.Button(
        leiste,
        text=get_string("kalender.pause_button", locale),
        command=lambda: None,
        font=("Segoe UI", 10),
        padx=10,
        pady=2,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    _taste_grundstil(pause_btn, basis_bg=kf0.HINTERGRUND_FENSTER)
    _taste_hover_binden(pause_btn, basis_bg=kf0.HINTERGRUND_FENSTER)
    pause_btn.pack(side=tk.RIGHT, padx=(0, 6))

    fenster_hintergrund_setzen()

    def nach_erscheinungsmodus_global() -> None:
        fenster_hintergrund_setzen()
        kf_nm = kalender_farben()
        _taste_grundstil(einstellungen_btn, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _taste_hover_binden(einstellungen_btn, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _taste_grundstil(pause_btn, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _taste_hover_binden(pause_btn, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _taste_grundstil(btn_raster_layout, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _taste_hover_binden(btn_raster_layout, basis_bg=kf_nm.HINTERGRUND_FENSTER)
        _toggle_sync(
            monat_ws_buttons,
            var_monat_ws.get(),
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
        )
        _toggle_sync(
            monat_rand_buttons,
            var_monat_rand.get(),
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
        )
        _toggle_sync(
            woche_art_buttons,
            var_woche_art.get(),
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
        )
        _taste_hover_binden(
            b_monat_mo,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_monat_ws.get() == "mo",
        )
        _taste_hover_binden(
            b_monat_so,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_monat_ws.get() == "so",
        )
        _taste_hover_binden(
            b_rand_ohne,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_monat_rand.get() == "ohne",
        )
        _taste_hover_binden(
            b_rand_mit,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_monat_rand.get() == "mit",
        )
        _taste_hover_binden(
            b_woche_mitte,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_woche_art.get() == "mitte",
        )
        _taste_hover_binden(
            b_woche_mo_so,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_woche_art.get() == "mo_so",
        )
        _taste_hover_binden(
            b_woche_so_sa,
            basis_bg=kf_nm.HINTERGRUND_FENSTER,
            ist_aktiv=lambda: var_woche_art.get() == "so_sa",
        )
        ansicht.darstellung_auffrischen()

    return KalenderDemoHandle(
        ansicht=ansicht,
        nach_erscheinungsmodus_global=nach_erscheinungsmodus_global,
    )


def run_demo(locale: str = "de") -> None:
    root = tk.Tk()
    version_info = load_version_info()
    root.title(
        fenster_titel(
            basis_titel=get_string("kalender.fenster_titel", locale),
            version_info=version_info,
            benutzer="Gast",
            geoeffnet_um=zeitstempel_jetzt(),
            locale=locale,
        )
    )
    root.geometry("1280x720")
    root.minsize(720, 420)

    haupt = tk.Frame(root, highlightthickness=0)
    haupt.pack(fill=tk.BOTH, expand=True)

    handle = kalender_demo_in(haupt, locale)

    kf = kalender_farben()
    fuss = tk.Frame(root, bg=kf.HINTERGRUND_ZEITLEISTE, height=40)
    fuss.pack(side=tk.BOTTOM, fill=tk.X)
    fuss.pack_propagate(False)

    def modus_symbol_aktuell() -> str:
        return "\u263e" if not ist_darkmode() else "\u2600"

    def _modus_btn_stil_setzen() -> None:
        kf_local = kalender_farben()
        modus_btn.configure(
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=kf_local.HINTERGRUND_ZEITLEISTE,
            fg=kf_local.TEXT_ZEIT,
            activebackground=kf_local.HINTERGRUND_ZEITLEISTE,
            activeforeground=kf_local.TEXT_ZEIT,
        )

    def _modus_btn_hover_binden() -> None:
        def _ein(_event: tk.Event | None = None) -> None:
            kf_local = kalender_farben()
            modus_btn.configure(
                bg=hex_rgb_mit_faktor(kf_local.HINTERGRUND_ZEITLEISTE, 0.93)
            )

        def _aus(_event: tk.Event | None = None) -> None:
            kf_local = kalender_farben()
            modus_btn.configure(bg=kf_local.HINTERGRUND_ZEITLEISTE)

        modus_btn.bind("<Enter>", _ein)
        modus_btn.bind("<Leave>", _aus)

    _icon_font = tkfont.Font(root, family="Segoe UI", size=14)
    modus_btn = tk.Button(
        fuss,
        text=modus_symbol_aktuell(),
        font=_icon_font,
        width=3,
    )
    _modus_btn_stil_setzen()
    _modus_btn_hover_binden()

    def bei_modus_standalone() -> None:
        toggle_modus()
        kf2 = kalender_farben()
        root.configure(bg=kf2.HINTERGRUND_FENSTER)
        haupt.configure(bg=kf2.HINTERGRUND_FENSTER)
        fuss.configure(bg=kf2.HINTERGRUND_ZEITLEISTE)
        modus_btn.configure(
            text=modus_symbol_aktuell(),
        )
        _modus_btn_stil_setzen()
        _modus_btn_hover_binden()
        handle.nach_erscheinungsmodus_global()

    modus_btn.configure(command=bei_modus_standalone)
    modus_btn.pack(side=tk.RIGHT, padx=8, pady=4)

    root.mainloop()
