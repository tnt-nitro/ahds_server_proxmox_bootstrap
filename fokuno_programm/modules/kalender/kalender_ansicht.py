"""Kalender: Tag, Mehrtag, Monat oder Jahr."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from enum import Enum, auto
import tkinter as tk
import tkinter.font as tkfont
from typing import Any
from zoneinfo import ZoneInfo

from locales import get_string
from modules.arbeitszeit.regelprofil import RegelarbeitsProfil
from modules.pausenzeit.profil import PausenProfil
from modules.sonnenzeit.standort import StandortProfil, standard_frankfurt_am_main
from modules.theming.farben import kalender_farben
from modules.userzeit.wachzeit import PhasenFarben, WachzeitProfil
from modules.wegezeit.profil import WegezeitProfil

from .jahres_raster import JahresRasterAnsicht
from .monats_raster import (
    KalenderMonatRanddarstellung,
    KalenderMonatWochenstart,
    MonatsRasterAnsicht,
)
from .farb_hilfen import MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR, hex_rgb_mit_faktor
from .tagesansicht import KalenderRasterModus, Tagesansicht, ZoomStufe


def _text_mehrtag_kopfzeile(d: dt.date, locale: str) -> str:
    """Eine Zeile: Kurz-Wochentag, Datum, ISO-KW (für Mehrtage nebeneinander)."""
    kurz = get_string(f"kalender.wochentag_kurz.{d.weekday()}", locale)
    kw = d.isocalendar()[1]
    kw_pr = get_string("kalender.kw_prefix", locale)
    return f"{kurz} {d.day}. {d.month}. {d.year}  {kw_pr}{kw:02d}"


def _text_drei_tage_kopfzeile(d: dt.date, locale: str) -> str:
    """Eine Zeile: ausgeschriebener Wochentag + ausgeschriebener Monat + ISO-KW (3 Tage nebeneinander)."""
    wt = get_string(f"kalender.wochentag_lang.{d.weekday()}", locale)
    mon = get_string(f"kalender.monat_lang.{d.month}", locale)
    kw = d.isocalendar()[1]
    kw_pr = get_string("kalender.kw_prefix", locale)
    if locale == "de":
        return f"{wt} {d.day}. {mon} {d.year}  {kw_pr}{kw:02d}"
    return f"{wt} {d.day} {mon} {d.year}  {kw_pr}{kw:02d}"


def _text_datum_lang(d: dt.date, locale: str) -> str:
    """Ausgeschriebenes Datum für Bereichs-Kopfzeilen."""
    wt = get_string(f"kalender.wochentag_lang.{d.weekday()}", locale)
    mon = get_string(f"kalender.monat_lang.{d.month}", locale)
    if locale == "de":
        return f"{wt} {d.day}. {mon} {d.year}"
    return f"{wt} {d.day} {mon} {d.year}"


def _text_von_bis_fest(von: str, bis: str) -> str:
    """Festes Zweifeld-Layout als eine Zeile; ``Bis`` startet stets an derselben Textspalte."""
    return f"Von: {von:<44}Bis: {bis}"


class KalenderWocheArt(Enum):
    """Sieben-Tage-Fenster bei Wochen-Raster (Ankertag = ``mitte_datum`` / Navigation)."""

    #: Drei Tage links, Anker in der Mitte, drei rechts.
    MITTE_SIEBEN_TAGE = auto()
    #: ISO üblich in Europa: Montag … Sonntag (Kalenderwoche).
    MONTAG_BIS_SONNTAG = auto()
    #: Oft in den USA: Sonntag … Samstag.
    SONNTAG_BIS_SAMSTAG = auto()


class KalenderAnsicht(tk.Frame):
    """Rahmen um eine oder mehrere :class:`Tagesansicht`; Zoom bei Mehrfachansicht gemeinsam."""
    VON_BIS_KOPF_FONT = ("Segoe UI", 10, "bold")

    def __init__(
        self,
        master: tk.Misc,
        mitte_datum: dt.date,
        wachzeit: WachzeitProfil,
        *,
        raster_modus: KalenderRasterModus = KalenderRasterModus.DREI_TAGE_HORIZONTAL,
        woche_art: KalenderWocheArt = KalenderWocheArt.MITTE_SIEBEN_TAGE,
        monat_wochenstart: KalenderMonatWochenstart = KalenderMonatWochenstart.MONTAG,
        monat_rand: KalenderMonatRanddarstellung = KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN,
        monat_jahr_layout_transponiert: bool = False,
        locale: str = "de",
        start_zoom: ZoomStufe = ZoomStufe.GANZTAG,
        phasen_farben: PhasenFarben | None = None,
        regelarbeit: RegelarbeitsProfil | None = None,
        wegezeit: WegezeitProfil | None = None,
        pausen: PausenProfil | None = None,
        standort: StandortProfil | None = None,
        mit_sonnenspalte: bool = True,
        mit_sonnenzeit_vorsaetzen: bool = False,
        jetzt_bannerschild_anzeigen: bool = True,
        jetzt_banner_wochentag: bool = True,
        jetzt_banner_tag: bool = True,
        jetzt_banner_monat: bool = True,
        jetzt_banner_jahr: bool = True,
        jetzt_banner_uhrzeit: bool = True,
        on_mehrtag_datum_einzel_tag: Callable[[dt.date], None] | None = None,
        on_kw_woche: Callable[[dt.date], None] | None = None,
        on_jahr_monat: Callable[[dt.date], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._mitte_datum = mitte_datum
        self._wachzeit = wachzeit
        self._raster_modus = raster_modus
        self._woche_art = woche_art
        self._monat_wochenstart = monat_wochenstart
        self._monat_rand = monat_rand
        self._monat_jahr_layout_transponiert = monat_jahr_layout_transponiert
        self._start_zoom = start_zoom
        self._monat_streifen_zoom: ZoomStufe = start_zoom
        self._monats_raster: MonatsRasterAnsicht | None = None
        self._jahres_raster: JahresRasterAnsicht | None = None
        self._tag_bau_args: dict[str, Any] = {
            "locale": locale,
            "start_zoom": start_zoom,
            "phasen_farben": phasen_farben,
            "regelarbeit": regelarbeit,
            "wegezeit": wegezeit,
            "pausen": pausen,
            "standort": standort,
            "mit_sonnenspalte": mit_sonnenspalte,
            "mit_sonnenzeit_vorsaetzen": mit_sonnenzeit_vorsaetzen,
            "jetzt_bannerschild_anzeigen": jetzt_bannerschild_anzeigen,
            "jetzt_banner_wochentag": jetzt_banner_wochentag,
            "jetzt_banner_tag": jetzt_banner_tag,
            "jetzt_banner_monat": jetzt_banner_monat,
            "jetzt_banner_jahr": jetzt_banner_jahr,
            "jetzt_banner_uhrzeit": jetzt_banner_uhrzeit,
        }
        self._on_mehrtag_datum_einzel_tag = on_mehrtag_datum_einzel_tag
        self._on_kw_woche = on_kw_woche
        self._on_jahr_monat = on_jahr_monat
        self._modus_kopf_padx = 8
        self._modus_kopf = tk.Label(
            self,
            bd=0,
            highlightthickness=0,
            anchor=tk.W,
            padx=8,
            pady=4,
            font=("Segoe UI", 10, "bold"),
        )
        self._innen = tk.Frame(self)
        self._innen.pack(fill=tk.BOTH, expand=True)
        self._tag_views: list[Tagesansicht] = []
        #: Horizontal Mehrtag: zuletzt verarbeitete (Breite, Höhe, n) für place-Layout.
        self._horizontal_place_key: tuple[int, int, int] | None = None
        self._innen.bind("<Configure>", self._bei_innen_configure)
        self._aufbauen()

    def _modus_kopf_text(self) -> str | None:
        loc = self._tag_bau_args["locale"]
        d = self._mitte_datum
        if self._raster_modus is KalenderRasterModus.EIN_TAG:
            wt = get_string(f"kalender.wochentag_lang.{d.weekday()}", loc)
            mon = get_string(f"kalender.monat_lang.{d.month}", loc)
            kw = d.isocalendar()[1]
            kw_pr = get_string("kalender.kw_prefix", loc)
            if loc == "de":
                return f"{wt} {d.day}. {mon} {d.year}  {kw_pr}{kw:02d}"
            return f"{wt} {d.day} {mon} {d.year}  {kw_pr}{kw:02d}"
        if self._raster_modus is KalenderRasterModus.MONAT:
            mon = get_string(f"kalender.monat_lang.{d.month}", loc)
            return f"{mon} {d.year}"
        if self._raster_modus is KalenderRasterModus.JAHR:
            return str(d.year)
        if self._raster_modus is KalenderRasterModus.DREI_TAGE_VERTIKAL:
            von, _, bis = self._drei_tage_daten()
            return _text_von_bis_fest(
                _text_datum_lang(von, loc),
                _text_datum_lang(bis, loc),
            )
        if self._raster_modus in (
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            daten = (
                self._wochen_daten()
                if self._raster_modus is KalenderRasterModus.WOCHE_VERTIKAL
                else self._arbeitswochen_daten()
            )
            return _text_von_bis_fest(
                _text_datum_lang(daten[0], loc),
                _text_datum_lang(daten[-1], loc),
            )
        if self._raster_modus is KalenderRasterModus.WOCHENENDE_VERTIKAL:
            sa, so = self._wochenende_daten()
            return _text_von_bis_fest(
                _text_datum_lang(sa, loc),
                _text_datum_lang(so, loc),
            )
        return None

    def _ist_vertikaler_von_bis_bereich(self) -> bool:
        return self._raster_modus in (
            KalenderRasterModus.DREI_TAGE_VERTIKAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
        )

    def _modus_kopf_sync(self) -> None:
        txt = self._modus_kopf_text()
        if not txt:
            self._modus_kopf.unbind("<Button-1>")
            self._modus_kopf.unbind("<Enter>")
            self._modus_kopf.unbind("<Leave>")
            self._modus_kopf.configure(cursor="")
            self._modus_kopf.pack_forget()
            return
        kf = kalender_farben()
        pad = 8
        if self._raster_modus is KalenderRasterModus.EIN_TAG:
            # Tagansicht: Kopf beginnt am farbigen Kalenderblatt (rechts von Zeitleiste/Sonne).
            pad = self._linke_zeitleiste_sonne_breite_px() + 6
        elif self._ist_vertikaler_von_bis_bereich():
            # Vertikale Bereichsansichten: alle exakt gleich ausgerichtet.
            pad = self._linke_zeitleiste_sonne_breite_px() + 6
        elif self._raster_modus is KalenderRasterModus.MONAT:
            # Monatsansicht: links Zeitleisten-Streifen + KW-Spalte vor den Tageszellen.
            pad = self._linke_zeitleiste_sonne_breite_px() + 44 + 6
        font = ("Segoe UI", 10, "bold")
        if self._ist_vertikaler_von_bis_bereich():
            # Monospace für stabiles Spaltenlayout von "Von" / "Bis".
            font = self.VON_BIS_KOPF_FONT
        self._modus_kopf_padx = pad
        self._modus_kopf.configure(
            text=txt,
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            padx=pad,
            font=font,
        )
        self._modus_kopf.pack(fill=tk.X, side=tk.TOP, before=self._innen)
        self._modus_kopf.unbind("<Button-1>")
        self._modus_kopf.unbind("<Enter>")
        self._modus_kopf.unbind("<Leave>")
        self._modus_kopf.configure(cursor="")
        if (
            self._on_mehrtag_datum_einzel_tag is not None
            and self._ist_vertikaler_von_bis_bereich()
        ):
            self._modus_kopf.bind("<Button-1>", self._bei_modus_kopf_von_bis_klick)
            self._modus_kopf.bind("<Enter>", self._modus_kopf_hover_enter)
            self._modus_kopf.bind("<Leave>", self._modus_kopf_hover_leave)
            self._modus_kopf.configure(cursor="hand2")

    def _modus_kopf_hover_enter(self, _event: tk.Event | None = None) -> None:
        if self._on_mehrtag_datum_einzel_tag is None:
            return
        kf = kalender_farben()
        self._modus_kopf.configure(
            bg=hex_rgb_mit_faktor(
                kf.HINTERGRUND_ZEITLEISTE, MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR
            )
        )

    def _modus_kopf_hover_leave(self, _event: tk.Event | None = None) -> None:
        kf = kalender_farben()
        self._modus_kopf.configure(bg=kf.HINTERGRUND_ZEITLEISTE)

    def _modus_kopf_von_bis_datumspaar(self) -> tuple[dt.date, dt.date] | None:
        if self._raster_modus is KalenderRasterModus.DREI_TAGE_VERTIKAL:
            a, _, b = self._drei_tage_daten()
            return (a, b)
        if self._raster_modus in (
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            daten = (
                self._wochen_daten()
                if self._raster_modus is KalenderRasterModus.WOCHE_VERTIKAL
                else self._arbeitswochen_daten()
            )
            return (daten[0], daten[-1])
        if self._raster_modus is KalenderRasterModus.WOCHENENDE_VERTIKAL:
            sa, so = self._wochenende_daten()
            return (sa, so)
        return None

    def _bei_modus_kopf_von_bis_klick(self, event: tk.Event) -> None:
        if self._on_mehrtag_datum_einzel_tag is None:
            return
        paar = self._modus_kopf_von_bis_datumspaar()
        if paar is None:
            return
        von_d, bis_d = paar
        loc = self._tag_bau_args["locale"]
        von_t = _text_datum_lang(von_d, loc)
        bis_t = _text_datum_lang(bis_d, loc)
        f = tkfont.Font(font=self.VON_BIS_KOPF_FONT)
        grenze_px = f.measure("Von: " + f"{von_t:<44}")
        x_text = event.x - int(self._modus_kopf_padx)
        if x_text < grenze_px:
            self._on_mehrtag_datum_einzel_tag(von_d)
        else:
            self._on_mehrtag_datum_einzel_tag(bis_d)

    def _heute_im_ansicht(self) -> dt.date:
        st = self._tag_bau_args.get("standort") or standard_frankfurt_am_main()
        return dt.datetime.now(ZoneInfo(st.zeitzone)).date()

    def _bei_monatszelle(self, d: dt.date) -> None:
        self._mitte_datum = d
        if self._monats_raster is None:
            return
        oy, om = self._monats_raster.jahr_monat
        if d.year != oy or d.month != om:
            self._monats_raster.monat_setzen(d)
        else:
            self._monats_raster.darstellung_auffrischen()

    def _bei_jahreszelle(self, d: dt.date) -> None:
        self._mitte_datum = d
        if self._jahres_raster is None:
            return
        if d.year != self._jahres_raster.jahr:
            self._jahres_raster.jahr_setzen(d)
        else:
            self._jahres_raster.darstellung_auffrischen()

    def _zoom_zum_aufbau(self) -> ZoomStufe:
        if not self._tag_views:
            return self._start_zoom
        n = len(self._tag_views)
        if n in (3, 7):
            return self._tag_views[n // 2].zoom
        return self._tag_views[0].zoom

    def _stunden_raster_intervall_aktuell(self) -> int:
        if self._raster_modus in (
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            return 4
        if self._raster_modus in (
            KalenderRasterModus.DREI_TAGE_VERTIKAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
        ):
            return 2
        return 1

    def _drei_tage_daten(self) -> tuple[dt.date, dt.date, dt.date]:
        d = self._mitte_datum
        return (
            d - dt.timedelta(days=1),
            d,
            d + dt.timedelta(days=1),
        )

    def _wochen_daten(self) -> tuple[dt.date, ...]:
        d = self._mitte_datum
        if self._woche_art is KalenderWocheArt.MITTE_SIEBEN_TAGE:
            return tuple(d + dt.timedelta(days=i) for i in range(-3, 4))
        if self._woche_art is KalenderWocheArt.MONTAG_BIS_SONNTAG:
            montag = d - dt.timedelta(days=d.weekday())
            return tuple(montag + dt.timedelta(days=i) for i in range(7))
        so = d - dt.timedelta(days=(d.weekday() + 1) % 7)
        return tuple(so + dt.timedelta(days=i) for i in range(7))

    def _arbeitswochen_daten(self) -> tuple[dt.date, ...]:
        """Montag bis Freitag der ISO-Woche, die ``mitte_datum`` enthält."""
        d = self._mitte_datum
        montag = d - dt.timedelta(days=d.weekday())
        return tuple(montag + dt.timedelta(days=i) for i in range(5))

    def _wochenende_daten(self) -> tuple[dt.date, dt.date]:
        """Samstag und Sonntag der ISO-Woche (Mo–So), die ``mitte_datum`` enthält."""
        d = self._mitte_datum
        montag = d - dt.timedelta(days=d.weekday())
        sa = montag + dt.timedelta(days=5)
        so = montag + dt.timedelta(days=6)
        return (sa, so)

    def _neue_tagesansicht(
        self,
        datum: dt.date,
        zoom: ZoomStufe,
        *,
        master: tk.Misc | None = None,
        **extras: Any,
    ) -> Tagesansicht:
        opt = {
            **self._tag_bau_args,
            "start_zoom": zoom,
            "stunden_raster_intervall": self._stunden_raster_intervall_aktuell(),
            "kalender_raster_modus": self._raster_modus,
            **extras,
        }
        parent = self._innen if master is None else master
        return Tagesansicht(parent, datum, self._wachzeit, **opt)

    def _monat_streifen_nach_aufbau_sync(self) -> None:
        if self._monats_raster is None:
            self._tag_views = []
            return
        alle = list(self._monats_raster.streifen_ansichten)
        gruppe = tuple(alle)
        for tv in alle:
            tv.zoom_sync_gruppe_setzen(gruppe)
        self._tag_views = alle

    def _linke_zeitleiste_sonne_breite_px(self) -> int:
        """Breite der Zeitleiste + Sonnenspalte wie in Spalte 0 (nebeneinander)."""
        b = Tagesansicht.ZEITLEISTE_TEXT_BREITE
        if self._tag_bau_args.get("mit_sonnenspalte", True):
            b += Tagesansicht.SONNENSPALT_BREITE
        return b

    def _horizontal_tagesansichten_platzieren(self) -> None:
        """Pixelgenau: Kalenderblatt k je Tag, erste Fläche k+L (Zeitleiste L)."""
        if self._raster_modus not in (
            KalenderRasterModus.DREI_TAGE_HORIZONTAL,
            KalenderRasterModus.WOCHENENDE_HORIZONTAL,
            KalenderRasterModus.WOCHE_HORIZONTAL,
            KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
        ):
            return
        n = len(self._tag_views)
        if n <= 0:
            return
        try:
            self.update_idletasks()
            W = self._innen.winfo_width()
            H = max(self._innen.winfo_height(), 1)
        except tk.TclError:
            return
        if W <= 1:
            return
        key = (W, H, n)
        if key == self._horizontal_place_key:
            return
        self._horizontal_place_key = key
        L = float(self._linke_zeitleiste_sonne_breite_px())
        k = (float(W) - L) / float(n)
        if k < 1.0:
            k = 1.0
        x = 0
        for i, v in enumerate(self._tag_views):
            if i == n - 1:
                wi = max(1, W - x)
            elif i == 0:
                wi = int(round(k + L))
            else:
                wi = int(round(k))
            v.place(x=x, y=0, width=wi, height=H, anchor="nw")
            x += wi

    def _bei_innen_configure(self, _event: tk.Event) -> None:
        self._horizontal_tagesansichten_platzieren()
        if self._raster_modus is KalenderRasterModus.MONAT and self._monats_raster is not None:
            try:
                w = self._innen.winfo_width()
                h = self._innen.winfo_height()
            except tk.TclError:
                return
            if w > 1 and h > 1:
                self._monats_raster.layout_nach_elterngroesse()
        if self._raster_modus is KalenderRasterModus.JAHR and self._jahres_raster is not None:
            try:
                w = self._innen.winfo_width()
                h = self._innen.winfo_height()
            except tk.TclError:
                return
            if w > 1 and h > 1:
                self._jahres_raster.layout_nach_elterngroesse()

    def _aufbauen(self) -> None:
        self._modus_kopf_sync()
        z = self._zoom_zum_aufbau()
        self._horizontal_place_key = None
        self._monats_raster = None
        self._jahres_raster = None
        for w in self._innen.winfo_children():
            w.destroy()
        self._tag_views = []
        for i in range(16):
            self._innen.grid_rowconfigure(i, weight=0)
            self._innen.grid_columnconfigure(i, weight=0, minsize=0)

        if self._raster_modus is KalenderRasterModus.EIN_TAG:
            v = self._neue_tagesansicht(self._mitte_datum, z)
            v.pack(fill=tk.BOTH, expand=True)
            v.zoom_sync_gruppe_setzen(None)
            self._tag_views = [v]
            return

        if self._raster_modus is KalenderRasterModus.JAHR:
            self._jahres_raster = JahresRasterAnsicht(
                self._innen,
                self._mitte_datum,
                self._monat_wochenstart,
                self._monat_rand,
                locale=self._tag_bau_args["locale"],
                on_tag=self._bei_jahreszelle,
                on_tag_einzelansicht=self._on_mehrtag_datum_einzel_tag,
                on_monat_titel=self._on_jahr_monat,
                on_kw_zeile=self._on_kw_woche,
                transpose=self._monat_jahr_layout_transponiert,
            )
            self._jahres_raster.pack(fill=tk.BOTH, expand=True)
            self._tag_views = []
            return

        if self._raster_modus is KalenderRasterModus.MONAT:
            self._monat_streifen_zoom = z
            L = self._linke_zeitleiste_sonne_breite_px()

            def streifen_bau(m: tk.Misc, ref: dt.date) -> Tagesansicht:
                return self._neue_tagesansicht(
                    ref,
                    self._monat_streifen_zoom,
                    master=m,
                    width=L,
                    kalender_raster_modus=KalenderRasterModus.EIN_TAG,
                    stunden_raster_intervall=4,
                    rand_rechts_px=0,
                    kalenderblatt_zeigen=False,
                    periodisches_neuzeichnen=False,
                )

            self._monats_raster = MonatsRasterAnsicht(
                self._innen,
                self._mitte_datum,
                self._monat_wochenstart,
                self._monat_rand,
                locale=self._tag_bau_args["locale"],
                on_tag=self._bei_monatszelle,
                on_tag_einzelansicht=self._on_mehrtag_datum_einzel_tag,
                on_kw_zeile=self._on_kw_woche,
                streifen_bau=streifen_bau,
                streifen_breite_px=L,
                transpose=self._monat_jahr_layout_transponiert,
            )
            self._monats_raster.pack(fill=tk.BOTH, expand=True)
            self._monat_streifen_nach_aufbau_sync()
            return

        if self._raster_modus in (
            KalenderRasterModus.DREI_TAGE_HORIZONTAL,
            KalenderRasterModus.DREI_TAGE_VERTIKAL,
        ):
            daten = self._drei_tage_daten()
            horizontal = self._raster_modus is KalenderRasterModus.DREI_TAGE_HORIZONTAL
        elif self._raster_modus in (
            KalenderRasterModus.WOCHENENDE_HORIZONTAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
        ):
            daten = self._wochenende_daten()
            horizontal = self._raster_modus is KalenderRasterModus.WOCHENENDE_HORIZONTAL
        elif self._raster_modus in (
            KalenderRasterModus.WOCHE_HORIZONTAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
        ):
            daten = self._wochen_daten()
            horizontal = self._raster_modus is KalenderRasterModus.WOCHE_HORIZONTAL
        elif self._raster_modus in (
            KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            daten = self._arbeitswochen_daten()
            horizontal = (
                self._raster_modus is KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL
            )
        else:
            raise AssertionError(self._raster_modus)

        mehrtage_band = self._raster_modus in (
            KalenderRasterModus.DREI_TAGE_HORIZONTAL,
            KalenderRasterModus.DREI_TAGE_VERTIKAL,
            KalenderRasterModus.WOCHENENDE_HORIZONTAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
            KalenderRasterModus.WOCHE_HORIZONTAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        )
        n_tage = len(daten)
        views: list[Tagesansicht] = []
        for i, d in enumerate(daten):
            extras: dict[str, Any] = {}
            if mehrtage_band:
                # Nebeneinander: Zeitleiste/Sonne nur links (Spalte 0); übereinander: jeder Tag.
                extras["mit_zeitleiste_und_sonne"] = (not horizontal) or (i == 0)
                if horizontal:
                    if i < n_tage - 1:
                        extras["rand_rechts_px"] = 0
                    if i > 0:
                        extras["woche_tag_trennung_links"] = True
                    loc = self._tag_bau_args["locale"]
                    if self._raster_modus in (
                        KalenderRasterModus.DREI_TAGE_HORIZONTAL,
                        KalenderRasterModus.WOCHENENDE_HORIZONTAL,
                    ):
                        extras["mehrtag_kopfzeile_fn"] = (
                            lambda dd, l=loc: _text_drei_tage_kopfzeile(dd, l)
                        )
                    else:
                        extras["mehrtag_kopfzeile_fn"] = (
                            lambda dd, l=loc: _text_mehrtag_kopfzeile(dd, l)
                        )
                    extras["mehrtag_heute_fn"] = self._heute_im_ansicht
                    if self._on_mehrtag_datum_einzel_tag is not None:
                        extras["mehrtag_kopf_klick_einzel_tag"] = (
                            self._on_mehrtag_datum_einzel_tag
                        )
                else:
                    if i < n_tage - 1:
                        extras["rand_unten_px"] = 0
                    if i > 0:
                        extras["woche_tag_trennung_oben"] = True
            views.append(self._neue_tagesansicht(d, z, **extras))
        gruppe = tuple(views)
        for v in views:
            v.zoom_sync_gruppe_setzen(gruppe)

        if horizontal:
            n_h = len(views)
            if n_h > 0:
                #: place statt grid: Tk-Grid-Gewichte erzielen die k vs. k+L-Aufteilung hier nicht zuverlässig.
                def _place_nach_layout() -> None:
                    self._horizontal_tagesansichten_platzieren()
                    self.after(100, self._horizontal_tagesansichten_platzieren)

                self.after_idle(_place_nach_layout)
        else:
            for i, v in enumerate(views):
                v.grid(row=i, column=0, sticky="nsew")
                self._innen.grid_rowconfigure(i, weight=1)
            self._innen.grid_columnconfigure(0, weight=1)
        self._tag_views = views

    @property
    def raster_modus(self) -> KalenderRasterModus:
        return self._raster_modus

    @property
    def woche_art(self) -> KalenderWocheArt:
        return self._woche_art

    @property
    def datum(self) -> dt.date:
        return self._mitte_datum

    def raster_modus_setzen(self, neu: KalenderRasterModus) -> None:
        if neu is self._raster_modus:
            return
        self._raster_modus = neu
        self._aufbauen()

    def woche_art_setzen(self, neu: KalenderWocheArt) -> None:
        if neu is self._woche_art:
            return
        self._woche_art = neu
        if self._raster_modus in (
            KalenderRasterModus.WOCHE_HORIZONTAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
        ):
            self._aufbauen()

    def monat_wochenstart_setzen(self, ws: KalenderMonatWochenstart) -> None:
        if ws is self._monat_wochenstart:
            return
        self._monat_wochenstart = ws
        if self._raster_modus is KalenderRasterModus.MONAT and self._monats_raster is not None:
            if self._tag_views:
                self._monat_streifen_zoom = self._tag_views[0].zoom
            self._monats_raster.wochenstart_setzen(ws)
            self._monat_streifen_nach_aufbau_sync()
        elif self._raster_modus is KalenderRasterModus.JAHR and self._jahres_raster is not None:
            self._jahres_raster.wochenstart_setzen(ws)

    def monat_jahr_layout_transponiert_setzen(self, transponiert: bool) -> None:
        if transponiert is self._monat_jahr_layout_transponiert:
            return
        self._monat_jahr_layout_transponiert = transponiert
        if self._raster_modus is KalenderRasterModus.MONAT and self._monats_raster is not None:
            self._monats_raster.transpose_setzen(transponiert)
        elif self._raster_modus is KalenderRasterModus.JAHR and self._jahres_raster is not None:
            self._jahres_raster.transpose_setzen(transponiert)

    def monat_randdarstellung_setzen(self, r: KalenderMonatRanddarstellung) -> None:
        if r is self._monat_rand:
            return
        self._monat_rand = r
        if self._raster_modus is KalenderRasterModus.MONAT and self._monats_raster is not None:
            if self._tag_views:
                self._monat_streifen_zoom = self._tag_views[0].zoom
            self._monats_raster.randdarstellung_setzen(r)
            self._monat_streifen_nach_aufbau_sync()
        elif self._raster_modus is KalenderRasterModus.JAHR and self._jahres_raster is not None:
            self._jahres_raster.randdarstellung_setzen(r)

    def darstellung_auffrischen(self) -> None:
        self._modus_kopf_sync()
        if self._raster_modus is KalenderRasterModus.JAHR:
            if self._jahres_raster is not None:
                self._jahres_raster.darstellung_auffrischen()
            return
        if self._raster_modus is KalenderRasterModus.MONAT:
            if self._monats_raster is not None:
                self._monats_raster.darstellung_auffrischen()
            return
        for v in self._tag_views:
            v.darstellung_auffrischen()

    def datum_setzen(self, neu: dt.date) -> None:
        self._mitte_datum = neu
        self._modus_kopf_sync()
        if self._raster_modus is KalenderRasterModus.JAHR:
            if self._jahres_raster is not None:
                if neu.year != self._jahres_raster.jahr:
                    self._jahres_raster.jahr_setzen(neu)
                else:
                    self._jahres_raster.darstellung_auffrischen()
            return
        if self._raster_modus is KalenderRasterModus.MONAT:
            if self._monats_raster is not None:
                oy, om = self._monats_raster.jahr_monat
                if neu.year != oy or neu.month != om:
                    if self._tag_views:
                        self._monat_streifen_zoom = self._tag_views[0].zoom
                    self._monats_raster.monat_setzen(neu)
                    self._monat_streifen_nach_aufbau_sync()
                else:
                    self._monats_raster.darstellung_auffrischen()
            return
        if not self._tag_views:
            return
        if self._raster_modus is KalenderRasterModus.EIN_TAG:
            self._tag_views[0].datum_setzen(neu)
            return
        if self._raster_modus in (
            KalenderRasterModus.WOCHE_HORIZONTAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
        ):
            for v, d in zip(self._tag_views, self._wochen_daten()):
                v.datum_setzen(d)
            return
        if self._raster_modus in (
            KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            for v, d in zip(self._tag_views, self._arbeitswochen_daten()):
                v.datum_setzen(d)
            return
        if self._raster_modus in (
            KalenderRasterModus.WOCHENENDE_HORIZONTAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
        ):
            for v, d in zip(self._tag_views, self._wochenende_daten()):
                v.datum_setzen(d)
            return
        daten = self._drei_tage_daten()
        for v, d in zip(self._tag_views, daten):
            v.datum_setzen(d)

    def sonnenzeit_vorsaetze_setzen(self, sichtbar: bool) -> None:
        for v in self._tag_views:
            v.sonnenzeit_vorsaetze_setzen(sichtbar)

    def regelarbeit_setzen(self, profil: RegelarbeitsProfil) -> None:
        """Regelarbeitsprofil austauschen und Darstellung neu aufbauen."""
        self._tag_bau_args["regelarbeit"] = profil
        self._aufbauen()

    def pausen_setzen(self, profil: PausenProfil) -> None:
        """Pausenprofil austauschen und Darstellung neu aufbauen."""
        self._tag_bau_args["pausen"] = profil
        self._aufbauen()

    def jetzt_banner_einstellen(
        self,
        *,
        bannerschild_anzeigen: bool | None = None,
        wochentag: bool | None = None,
        tag: bool | None = None,
        monat: bool | None = None,
        jahr: bool | None = None,
        uhrzeit: bool | None = None,
    ) -> None:
        for v in self._tag_views:
            v.jetzt_banner_einstellen(
                bannerschild_anzeigen=bannerschild_anzeigen,
                wochentag=wochentag,
                tag=tag,
                monat=monat,
                jahr=jahr,
                uhrzeit=uhrzeit,
            )
