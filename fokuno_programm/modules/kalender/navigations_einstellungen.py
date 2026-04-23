"""Kalender: Zeitraum-Buttons und zugehörige Schnellwahl-Buttons."""

from __future__ import annotations

import datetime as dt
import tkinter as tk
from collections.abc import Callable
from enum import Enum, auto
from typing import Any

from locales import get_string
from modules.theming.farben import kalender_farben

from .farb_hilfen import hex_rgb_mit_faktor

from .navigation_datum import (
    KalenderNavigationIntervall,
    datum_diese_3_tage_erster,
    datum_diese_woche_montag,
    datum_dieser_monat_erster,
    datum_dieses_jahr_erster,
    datum_dieses_wochenende_samstag,
    datum_gestern,
    datum_heute,
    datum_kalenderjahr_schritt,
    datum_kalendermonat_schritt,
    datum_letzte_3_tage_erster,
    datum_letzte_woche_montag,
    datum_letzter_monat_erster,
    datum_letztes_jahr_erster,
    datum_letztes_wochenende_samstag,
    datum_morgen,
    datum_naechste_3_tage_erster,
    datum_naechste_woche_montag,
    datum_naechster_monat_erster,
    datum_naechstes_jahr_erster,
    datum_naechstes_wochenende_samstag,
)


class KalenderIntervallBeschriftung(Enum):
    """Beschriftungsstil für die Zeitraum-Auswahlbuttons."""

    WORT = auto()
    KUERZEL_DE = auto()
    ICON = auto()


class KalenderNavigationsleiste(tk.Frame):
    """Eine Zeile: links Zeitraum-Buttons, rechts Schnellwahl-Buttons und optionale Zusatzsteuerung."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        locale: str = "de",
        on_datum: Callable[[dt.date], None],
        on_intervall: Callable[[KalenderNavigationIntervall], None] | None = None,
        start_intervall: KalenderNavigationIntervall = KalenderNavigationIntervall.TAG,
        intervall_beschriftung: KalenderIntervallBeschriftung = KalenderIntervallBeschriftung.WORT,
        intervall_start_padx: int = 0,
        aktueller_tag_fn: Callable[[], dt.date] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._locale = locale
        self._on_datum = on_datum
        self._on_intervall = on_intervall
        self._intervall = start_intervall
        self._intervall_beschriftung = intervall_beschriftung
        self._intervall_start_padx = max(0, intervall_start_padx)
        kf = kalender_farben()
        self._btn_bg_normal = kf.HINTERGRUND_FENSTER
        self._btn_bg_hover = hex_rgb_mit_faktor(self._btn_bg_normal, 0.93)
        self._btn_bg_aktiv = hex_rgb_mit_faktor(self._btn_bg_normal, 0.88)
        self._btn_bg_aktiv_hover = hex_rgb_mit_faktor(self._btn_bg_normal, 0.84)
        self._btn_fg = kf.TEXT_ZEIT
        #: Aktuelles Ansichtsdatum (Kalender-Anker); Steuerung der « / »-Schritte je Zeitraum.
        self._aktueller_tag_fn = aktueller_tag_fn

        #: Erste Zeile: Zeitraum + Schnellwahl (rechtsbündig).
        zeile = tk.Frame(self)
        zeile.pack(fill=tk.X, anchor=tk.W)
        self._zeile_nav = zeile

        links = tk.Frame(zeile)
        links.pack(side=tk.LEFT, anchor=tk.W)
        self._intervall_buttons_rahmen = tk.Frame(links)
        self._intervall_buttons_rahmen.pack(side=tk.LEFT, padx=(self._intervall_start_padx, 0))
        self._intervall_buttons: dict[KalenderNavigationIntervall, tk.Button] = {}
        self._intervall_buttons_aufbauen()

        rechts = tk.Frame(zeile)
        rechts.pack(side=tk.RIGHT, anchor=tk.E)
        self._btn_links = tk.Frame(rechts)
        self._btn_links.pack(side=tk.LEFT)
        #: Kalender-Layout (z. B. Nebeneinander/Übereinander); zweite Zeile volle Breite,
        #: damit breite Monats-/Jahr-Steuerung nicht die Icon-Leiste der App verdrängt.
        self.rechts_neben_nav_buttons = tk.Frame(self)
        self.rechts_neben_nav_buttons.pack(fill=tk.X, pady=(4, 0), after=self._zeile_nav)
        self.rechts_neben_nav_buttons.pack_propagate(False)
        self._zeilenhoehe_px = 0

        self._buttons_neu_aufbauen()
        self.after_idle(self._zeilenhoehe_sync)

    def raster_layout_steuerung_einblenden(self) -> None:
        if not self.rechts_neben_nav_buttons.winfo_ismapped():
            self.rechts_neben_nav_buttons.pack(
                fill=tk.X, pady=(4, 0), after=self._zeile_nav
            )
        self._zeilenhoehe_sync()

    def raster_layout_steuerung_ausblenden(self) -> None:
        # Zweite Zeile bewusst sichtbar lassen: in allen Kalenderansichten gleiche Leistenhöhe.
        if not self.rechts_neben_nav_buttons.winfo_ismapped():
            self.rechts_neben_nav_buttons.pack(
                fill=tk.X, pady=(4, 0), after=self._zeile_nav
            )
        self._zeilenhoehe_sync()

    def _zeilenhoehe_sync(self) -> None:
        """Zweite Navigationszeile auf Höhe der oberen Zeile halten (auch wenn unten leer)."""
        try:
            self.update_idletasks()
            oben = max(self._zeile_nav.winfo_reqheight(), self._zeile_nav.winfo_height())
        except tk.TclError:
            return
        if oben <= 1:
            return
        self._zeilenhoehe_px = max(self._zeilenhoehe_px, oben)
        self.rechts_neben_nav_buttons.configure(height=self._zeilenhoehe_px)

    def _intervall_tabelle(self) -> tuple[KalenderNavigationIntervall, ...]:
        return (
            KalenderNavigationIntervall.TAG,
            KalenderNavigationIntervall.DREI_TAGE,
            KalenderNavigationIntervall.WOCHE,
            KalenderNavigationIntervall.WOCHENENDE,
            KalenderNavigationIntervall.ARBEITSWOCHE,
            KalenderNavigationIntervall.MONAT,
            KalenderNavigationIntervall.JAHR,
        )

    def _text_fuer_intervall(self, iv: KalenderNavigationIntervall) -> str:
        if self._intervall_beschriftung is KalenderIntervallBeschriftung.KUERZEL_DE:
            kuerzel = {
                KalenderNavigationIntervall.TAG: "T",
                KalenderNavigationIntervall.DREI_TAGE: "3",
                KalenderNavigationIntervall.WOCHE: "W",
                KalenderNavigationIntervall.WOCHENENDE: "WE",
                KalenderNavigationIntervall.ARBEITSWOCHE: "AW",
                KalenderNavigationIntervall.MONAT: "M",
                KalenderNavigationIntervall.JAHR: "J",
            }
            return kuerzel[iv]
        if self._intervall_beschriftung is KalenderIntervallBeschriftung.ICON:
            icons = {
                KalenderNavigationIntervall.TAG: "\U0001F4C5",
                KalenderNavigationIntervall.DREI_TAGE: "3\U0001F4C5",
                KalenderNavigationIntervall.WOCHE: "\U0001F5D3",
                KalenderNavigationIntervall.WOCHENENDE: "\U0001F3D6",
                KalenderNavigationIntervall.ARBEITSWOCHE: "\U0001F4BC",
                KalenderNavigationIntervall.MONAT: "\U0001F4C6",
                KalenderNavigationIntervall.JAHR: "\U0001F5D2",
            }
            return icons[iv]
        schluessel = {
            KalenderNavigationIntervall.TAG: "kalender.nav_intervall.tag",
            KalenderNavigationIntervall.DREI_TAGE: "kalender.nav_intervall.drei_tage",
            KalenderNavigationIntervall.WOCHE: "kalender.nav_intervall.woche",
            KalenderNavigationIntervall.WOCHENENDE: "kalender.nav_intervall.wochenende",
            KalenderNavigationIntervall.ARBEITSWOCHE: "kalender.nav_intervall.arbeitswoche",
            KalenderNavigationIntervall.MONAT: "kalender.nav_intervall.monat",
            KalenderNavigationIntervall.JAHR: "kalender.nav_intervall.jahr",
        }
        return get_string(schluessel[iv], self._locale)

    def _intervall_buttons_aufbauen(self) -> None:
        for w in self._intervall_buttons_rahmen.winfo_children():
            w.destroy()
        self._intervall_buttons.clear()
        for iv in self._intervall_tabelle():
            b = self._taste_bauen(
                self._intervall_buttons_rahmen,
                text=self._text_fuer_intervall(iv),
                command=self._bei_intervall_button(iv),
                ist_aktiv=lambda i=iv: i is self._intervall,
            )
            b.pack(side=tk.LEFT, padx=(0, 4))
            self._intervall_buttons[iv] = b
        self._intervall_buttons_sync()

    def _intervall_buttons_sync(self) -> None:
        for iv, btn in self._intervall_buttons.items():
            ist_aktiv = iv is self._intervall
            btn.configure(
                text=self._text_fuer_intervall(iv),
                bg=self._btn_bg_aktiv if ist_aktiv else self._btn_bg_normal,
                activebackground=self._btn_bg_aktiv if ist_aktiv else self._btn_bg_normal,
            )

    def _taste_bauen(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Callable[[], None],
        ist_aktiv: Callable[[], bool] | None = None,
    ) -> tk.Button:
        b = tk.Button(
            master,
            text=text,
            command=command,
            padx=6,
            pady=1,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            bg=self._btn_bg_normal,
            fg=self._btn_fg,
            activebackground=self._btn_bg_normal,
            activeforeground=self._btn_fg,
        )

        def _hover_enter(_event: tk.Event | None = None) -> None:
            aktiv = ist_aktiv() if ist_aktiv is not None else False
            b.configure(bg=self._btn_bg_aktiv_hover if aktiv else self._btn_bg_hover)

        def _hover_leave(_event: tk.Event | None = None) -> None:
            aktiv = ist_aktiv() if ist_aktiv is not None else False
            b.configure(bg=self._btn_bg_aktiv if aktiv else self._btn_bg_normal)

        b.bind("<Enter>", _hover_enter)
        b.bind("<Leave>", _hover_leave)
        return b

    def _bei_intervall_button(self, iv: KalenderNavigationIntervall) -> Callable[[], None]:
        def _ruf() -> None:
            if iv is self._intervall:
                return
            self._intervall = iv
            self._intervall_buttons_sync()
            self._buttons_neu_aufbauen()
            if self._on_intervall is not None:
                self._on_intervall(self._intervall)

        return _ruf

    def intervall_beschriftung_setzen(self, neu: KalenderIntervallBeschriftung) -> None:
        if neu is self._intervall_beschriftung:
            return
        self._intervall_beschriftung = neu
        self._intervall_buttons_sync()

    def intervall_beschriftung(self) -> KalenderIntervallBeschriftung:
        return self._intervall_beschriftung

    def intervall_aktuell(self) -> KalenderNavigationIntervall:
        return self._intervall

    def intervall_programm_setzen(self, iv: KalenderNavigationIntervall) -> None:
        """Zeitraum per Code setzen (Buttons, Schnellbuttons, optional ``on_intervall``)."""
        if iv is self._intervall:
            return
        self._intervall = iv
        self._intervall_buttons_sync()
        self._buttons_neu_aufbauen()
        if self._on_intervall is not None:
            self._on_intervall(iv)

    def _buttons_neu_aufbauen(self) -> None:
        for w in self._btn_links.winfo_children():
            w.destroy()

        if self._intervall is KalenderNavigationIntervall.TAG:
            specs = [
                ("kalender.nav_btn.gestern", datum_gestern),
                ("kalender.nav_btn.heute", datum_heute),
                ("kalender.nav_btn.morgen", datum_morgen),
            ]
        elif self._intervall is KalenderNavigationIntervall.DREI_TAGE:
            specs = [
                ("kalender.nav_btn.letzte_3_tage", datum_letzte_3_tage_erster),
                ("kalender.nav_btn.diese_3_tage", datum_diese_3_tage_erster),
                ("kalender.nav_btn.naechste_3_tage", datum_naechste_3_tage_erster),
            ]
        elif self._intervall is KalenderNavigationIntervall.WOCHE:
            specs = [
                ("kalender.nav_btn.letzte_woche", datum_letzte_woche_montag),
                ("kalender.nav_btn.diese_woche", datum_diese_woche_montag),
                ("kalender.nav_btn.naechste_woche", datum_naechste_woche_montag),
            ]
        elif self._intervall is KalenderNavigationIntervall.ARBEITSWOCHE:
            specs = [
                (
                    "kalender.nav_btn.letzte_arbeitswoche",
                    datum_letzte_woche_montag,
                ),
                (
                    "kalender.nav_btn.diese_arbeitswoche",
                    datum_diese_woche_montag,
                ),
                (
                    "kalender.nav_btn.naechste_arbeitswoche",
                    datum_naechste_woche_montag,
                ),
            ]
        elif self._intervall is KalenderNavigationIntervall.WOCHENENDE:
            specs = [
                (
                    "kalender.nav_btn.wochenende_letztes",
                    datum_letztes_wochenende_samstag,
                ),
                (
                    "kalender.nav_btn.wochenende_dieses",
                    datum_dieses_wochenende_samstag,
                ),
                (
                    "kalender.nav_btn.wochenende_naechstes",
                    datum_naechstes_wochenende_samstag,
                ),
            ]
        elif self._intervall is KalenderNavigationIntervall.MONAT:
            specs = [
                ("kalender.nav_btn.letzter_monat", datum_letzter_monat_erster),
                ("kalender.nav_btn.dieser_monat", datum_dieser_monat_erster),
                ("kalender.nav_btn.naechster_monat", datum_naechster_monat_erster),
            ]
        elif self._intervall is KalenderNavigationIntervall.JAHR:
            specs = [
                ("kalender.nav_btn.letztes_jahr", datum_letztes_jahr_erster),
                ("kalender.nav_btn.dieses_jahr", datum_dieses_jahr_erster),
                ("kalender.nav_btn.naechstes_jahr", datum_naechstes_jahr_erster),
            ]
        else:
            raise AssertionError(self._intervall)

        if self._aktueller_tag_fn is not None:
            self._taste_bauen(
                self._btn_links,
                text=get_string("kalender.nav_btn.tag_blaettern_zurueck", self._locale),
                command=self._ansicht_schieben(-1),
            ).pack(side=tk.LEFT, padx=(0, 4), pady=0)

        for schluessel, fn in specs:
            b = self._taste_bauen(
                self._btn_links,
                text=get_string(schluessel, self._locale),
                command=self._befehl_datum(fn),
            )
            b.pack(side=tk.LEFT, padx=(0, 4), pady=0)

        if self._aktueller_tag_fn is not None:
            self._taste_bauen(
                self._btn_links,
                text=get_string("kalender.nav_btn.tag_blaettern_vor", self._locale),
                command=self._ansicht_schieben(1),
            ).pack(side=tk.LEFT, padx=(0, 4), pady=0)
        self.after_idle(self._zeilenhoehe_sync)

    def _ansicht_schieben(self, richtung: int) -> Callable[[], None]:
        def _ruf() -> None:
            tag_fn = self._aktueller_tag_fn
            assert tag_fn is not None
            basis = tag_fn()
            iv = self._intervall
            if iv is KalenderNavigationIntervall.TAG:
                neu = basis + dt.timedelta(days=richtung)
            elif iv is KalenderNavigationIntervall.DREI_TAGE:
                neu = basis + dt.timedelta(days=3 * richtung)
            elif iv in (
                KalenderNavigationIntervall.WOCHE,
                KalenderNavigationIntervall.ARBEITSWOCHE,
            ):
                neu = basis + dt.timedelta(days=7 * richtung)
            elif iv is KalenderNavigationIntervall.WOCHENENDE:
                neu = basis + dt.timedelta(days=7 * richtung)
            elif iv is KalenderNavigationIntervall.MONAT:
                neu = datum_kalendermonat_schritt(basis, richtung)
            elif iv is KalenderNavigationIntervall.JAHR:
                neu = datum_kalenderjahr_schritt(basis, richtung)
            else:
                raise AssertionError(iv)
            self._on_datum(neu)

        return _ruf

    def _befehl_datum(self, fn: Callable[[], dt.date]) -> Callable[[], None]:
        def _ruf() -> None:
            self._on_datum(fn())

        return _ruf
