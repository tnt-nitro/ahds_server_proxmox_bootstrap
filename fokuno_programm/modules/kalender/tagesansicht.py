"""Interaktives Kalenderblatt: Zeitleiste 00:00–24:00, Stundenraster, Jetzt-Zeiger, Zoom."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Callable
import tkinter as tk
from enum import Enum, auto
from typing import Any
from zoneinfo import ZoneInfo

import tkinter.font as tkfont

from locales import get_string, resolve_locale
from modules.arbeitszeit.regelprofil import RegelarbeitsProfil, standard_regelarbeit
from modules.pausenzeit.profil import PausenProfil, standard_arbeitspausen
from modules.sonnenzeit.berechnung import (
    datetime_aus_datum_und_minute_float,
    farbe_sonnenstreifen,
    helligkeit_01,
    nautische_daemmerung_am_tag,
    sonnen_kulmination_am_tag,
    sonnenzeiten_am_tag,
)
from modules.mondphasen import mondphase_synode_anteil, mondscheibe_zeichnen
from modules.sonnenzeit.standort import StandortProfil, standard_frankfurt_am_main
from modules.sonnenzeit.tk_sonne import sonne_zeitleiste_zeichnen
from modules.kalender.farb_hilfen import MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR, hex_rgb_mit_faktor
from modules.kalender.zeitaufzeichnung_speicher import (
    segmente_datetime_mitlauf,
    segmente_datetime_mitlauf_mit_titel,
    segmente_minuten_fuer_tag,
    segmente_minuten_mit_titel_fuer_tag,
)
from modules.krankmeldung.speicher import (
    eintrag_fuer_tag,
    ist_krankgeschrieben_am,
    ist_wiedervorstellung_am,
)
from modules.theming.farben import KalenderFarbenPaket, kalender_farben
from modules.wegezeit.profil import WegezeitProfil, standard_wegezeit
from modules.userzeit.wachzeit import PhasenFarben, WachzeitProfil, standard_phasen_farben
from modules.zeitumstellung import ZeitumstellungArt, umstellung_am_tag


class ZoomStufe(Enum):
    GANZTAG = auto()
    WACHZEIT = auto()
    MITLAUF = auto()


class KalenderRasterModus(Enum):
    """Ein Tag, Mehrtag, Monats- oder Jahresraster."""

    EIN_TAG = auto()
    DREI_TAGE_HORIZONTAL = auto()
    DREI_TAGE_VERTIKAL = auto()
    WOCHENENDE_HORIZONTAL = auto()
    WOCHENENDE_VERTIKAL = auto()
    WOCHE_HORIZONTAL = auto()
    WOCHE_VERTIKAL = auto()
    ARBEITSWOCHE_HORIZONTAL = auto()
    ARBEITSWOCHE_VERTIKAL = auto()
    MONAT = auto()
    JAHR = auto()


class Tagesansicht(tk.Frame):
    """Ein Tag: Uhrzeiten | optional Sonnenspalte | Kalenderblatt."""

    #: Graue Spalte: links Stunden, rechts Sonnenzeiten (genug Abstand ohne Überlagerung).
    ZEITLEISTE_TEXT_BREITE = 70
    #: Sonnenmarken (rechtsbündig) vor der Trennlinie zur Sonnenspalte.
    ZEITLEISTE_SONNENMARKEN_RAND = 6
    SONNENSPALT_BREITE = 5
    RAND_OBEN = 8
    RAND_UNTEN = 8
    RAND_RECHTS = 8
    JETZT_ZEIGER_HOEHE = 3
    MITLAUF_SPANNE_STUNDEN = 24
    MITLAUF_TAGWECHSEL_SCHWARZ = "#000000"
    #: Gemeinsamer Canvas-Tag für Jetzt-Linie und -Balken (tag_raise = oberste Ebene).
    JETZT_CANVAS_TAG = "jetzt_zeiger"
    MONDRADIUS = 14
    #: Vertikal: leicht über geometrischer Textmitte (Tk-Zentrierung wirkt oft etwas tief).
    MOND_UNTER_KULMINATION_OFFSET_Y = -0
    #: Mondmittelpunkt: links von der rechten Sonnenmarken-Kante (≈ halbe Textbreite HH:MM).
    MOND_CX_LINKS_VON_SONNENMARKE = 11
    SONNENRADIUS = 14
    #: Wie Mond: Mittelpunkt an der Oberkulminations-Uhrzeit.
    SONN_OBER_KULMINATION_OFFSET_Y = 0
    SONN_CX_LINKS_VON_SONNENMARKE = 11
    #: Zusatz für Strahlen beim Clipping (tk_sonne ``strahllaenge`` ≈ 3.5).
    SONN_STRAHL_CLIP_EXTRA = 5.0
    KRANKRAND_BREITE = 12
    KRANKRAND_FARBE = "#FFC000"
    KRANKRAND_AKZENT = "#FF8C00"
    ARZT_MARKER_FARBE = "#245B9E"
    ARZT_MARKER_TEXT = "A"
    JETZT_BANNER_FONT: tuple[str, int] = ("Segoe UI", 8)
    JETZT_BANNER_PAD_X = 6
    JETZT_BANNER_PAD_Y = 2
    #: Feste Pixelhöhe Mehrtag-Kopf (fetter „heute“-Text sonst Zeilenumbruch → gestauchtes Blatt).
    MEHRTAG_KOPF_RAHMEN_HOEHE_PX = 36

    @staticmethod
    def monats_wochentag_stundenlinien_y(hoehe: int) -> list[float]:
        """Y-Positionen für 4h-Raster in Monats-Wochentagszelle (ohne 0/24); wie Streifen-Zeitleiste."""
        y0 = float(Tagesansicht.RAND_OBEN)
        y1 = float(hoehe) - float(Tagesansicht.RAND_UNTEN)
        h_innen = max(y1 - y0, 1.0)
        ys: list[float] = []
        for stunde in range(0, 25, 4):
            if stunde in (0, 24):
                continue
            minute = stunde * 60
            ys.append(y0 + (minute / (24.0 * 60.0)) * h_innen)
        return ys

    @staticmethod
    def zeichne_jetzt_linie_in_tag_raster(
        c: tk.Canvas,
        kf: KalenderFarbenPaket,
        breite: int,
        hoehe: int,
        jetzt: dt.datetime,
        tag_kalendertag: dt.date,
        tz: ZoneInfo,
    ) -> None:
        """Nur die rote Jetzt-Linie (24h-Raster wie Monats-/Jahres-Tagzelle), ohne Bannerschild."""
        if jetzt.date() != tag_kalendertag:
            return
        y0 = float(Tagesansicht.RAND_OBEN)
        y1 = float(hoehe) - float(Tagesansicht.RAND_UNTEN)
        h_innen = max(y1 - y0, 1.0)
        mitternacht = dt.datetime.combine(tag_kalendertag, dt.time(0, 0), tzinfo=tz)
        minuten = (jetzt - mitternacht).total_seconds() / 60.0
        minuten = max(0.0, min(24.0 * 60.0, minuten))
        y_linie = y0 + (minuten / (24.0 * 60.0)) * h_innen
        c.create_line(
            0,
            y_linie,
            breite,
            y_linie,
            fill=kf.JETZT_ZEIGER,
            width=1,
            tags=(Tagesansicht.JETZT_CANVAS_TAG,),
        )

    def __init__(
        self,
        master: tk.Misc,
        datum: dt.date,
        wachzeit: WachzeitProfil,
        *,
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
        zoom_sync_gruppe: tuple["Tagesansicht", ...] | None = None,
        stunden_raster_intervall: int = 1,
        kalender_raster_modus: KalenderRasterModus = KalenderRasterModus.EIN_TAG,
        mit_zeitleiste_und_sonne: bool = True,
        rand_rechts_px: int | None = None,
        rand_unten_px: int | None = None,
        woche_tag_trennung_links: bool = False,
        woche_tag_trennung_oben: bool = False,
        periodisches_neuzeichnen: bool = True,
        kalenderblatt_zeigen: bool = True,
        mehrtag_kopfzeile_fn: Callable[[dt.date], str] | None = None,
        mehrtag_heute_fn: Callable[[], dt.date] | None = None,
        mehrtag_kopf_klick_einzel_tag: Callable[[dt.date], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._datum = datum
        self._wachzeit = wachzeit
        self._standort = standort if standort is not None else standard_frankfurt_am_main()
        self._mit_sonnenspalte = mit_sonnenspalte
        self._mit_zeitleiste_und_sonne = bool(mit_zeitleiste_und_sonne)
        self._rand_rechts = (
            self.RAND_RECHTS if rand_rechts_px is None else int(rand_rechts_px)
        )
        self._rand_unten = (
            self.RAND_UNTEN if rand_unten_px is None else int(rand_unten_px)
        )
        self._woche_tag_trennung_links = bool(woche_tag_trennung_links)
        self._woche_tag_trennung_oben = bool(woche_tag_trennung_oben)
        self._mit_sonnenzeit_vorsaetzen = mit_sonnenzeit_vorsaetzen
        self._jetzt_bannerschild_anzeigen = jetzt_bannerschild_anzeigen
        self._jetzt_banner_wochentag = jetzt_banner_wochentag
        self._jetzt_banner_tag = jetzt_banner_tag
        self._jetzt_banner_monat = jetzt_banner_monat
        self._jetzt_banner_jahr = jetzt_banner_jahr
        self._jetzt_banner_uhrzeit = jetzt_banner_uhrzeit
        self._jetzt_banner_font_tk: tkfont.Font | None = None
        self._regelarbeit = regelarbeit if regelarbeit is not None else standard_regelarbeit()
        self._wegezeit = wegezeit if wegezeit is not None else standard_wegezeit()
        self._pausenprofil = pausen if pausen is not None else standard_arbeitspausen()
        self._phasen_farben_override = phasen_farben
        self._locale = locale
        self._zoom = start_zoom
        self._zoom_sync_gruppe: tuple[Tagesansicht, ...] | None = zoom_sync_gruppe
        self._stunden_raster_intervall = max(1, int(stunden_raster_intervall))
        self._kalender_raster_modus = kalender_raster_modus
        self._kalenderblatt_zeigen = bool(kalenderblatt_zeigen)
        self._mehrtag_kopfzeile_fn = mehrtag_kopfzeile_fn
        self._mehrtag_heute_fn = mehrtag_heute_fn
        self._mehrtag_kopf_klick_einzel_tag = mehrtag_kopf_klick_einzel_tag
        self._mehrtag_kopf_label: tk.Label | None = None
        self._mehrtag_kopf_rahmen: tk.Frame | None = None
        #: Über der Zeitleiste/Sonne: fester Streifen, damit Hover/Kopf nur über dem Kalenderblatt wirkt.
        self._mehrtag_kopf_streifen_links: tk.Frame | None = None
        if mehrtag_kopfzeile_fn is not None:
            self._mehrtag_kopf_rahmen = tk.Frame(
                self,
                height=self.MEHRTAG_KOPF_RAHMEN_HOEHE_PX,
                bd=0,
                highlightthickness=0,
            )
            self._mehrtag_kopf_rahmen.pack(fill=tk.X, side=tk.TOP)
            self._mehrtag_kopf_rahmen.pack_propagate(False)
            self._mehrtag_sep_links: tk.Frame | None = None
            self._mehrtag_sep_zeitleiste: tk.Frame | None = None
            if self._woche_tag_trennung_links:
                self._mehrtag_sep_links = tk.Frame(
                    self._mehrtag_kopf_rahmen,
                    width=1,
                    bd=0,
                    highlightthickness=0,
                )
                self._mehrtag_sep_links.place(x=0, y=0, relheight=1.0)
            if self._mit_zeitleiste_und_sonne and self._kalenderblatt_zeigen:
                xk = self._x_kalender_start()
                self._mehrtag_kopf_streifen_links = tk.Frame(
                    self._mehrtag_kopf_rahmen,
                    width=xk,
                    bd=0,
                    highlightthickness=0,
                )
                self._mehrtag_kopf_streifen_links.pack(side=tk.LEFT, fill=tk.Y)
                self._mehrtag_kopf_streifen_links.pack_propagate(False)
                self._mehrtag_sep_zeitleiste = tk.Frame(
                    self._mehrtag_kopf_rahmen,
                    width=1,
                    bd=0,
                    highlightthickness=0,
                )
                self._mehrtag_sep_zeitleiste.place(x=xk, y=0, relheight=1.0)
            self._mehrtag_kopf_rahmen.bind("<Configure>", lambda e: self._mehrtag_kopf_layout_update())
            self._mehrtag_kopf_label = tk.Label(
                self._mehrtag_kopf_rahmen,
                bd=0,
                highlightthickness=0,
                anchor=tk.W,
                padx=6,
                pady=0,
            )
            self._mehrtag_kopf_refresh()
            self._mehrtag_kopf_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            if self._mehrtag_kopf_klick_einzel_tag is not None:
                self._mehrtag_kopf_label.bind(
                    "<Button-1>", self._bei_mehrtag_kopf_klick_einzel_tag
                )
                self._mehrtag_kopf_label.bind("<Enter>", self._mehrtag_kopf_hover_enter)
                self._mehrtag_kopf_label.bind("<Leave>", self._mehrtag_kopf_hover_leave)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        #: Monatsstreifen: ohne propagate würde die Canvas die Spalte aufblasen.
        if not bool(kalenderblatt_zeigen):
            self.pack_propagate(False)
        self._canvas.bind("<Configure>", self._bei_groessenwechsel)
        self._canvas.bind("<Motion>", self._bei_maus_bewegung)
        self._canvas.bind("<Leave>", self._bei_maus_verlassen)
        self._canvas.bind("<Button-1>", self._bei_klick)
        self._nach_update_id: str | None = None
        self._sichtbar_cache: tuple[float, float] | None = None
        self._krank_tooltip: tk.Toplevel | None = None
        self._krank_tooltip_text: str | None = None
        #: Nur während ``zeichne_monats_tag_zelle_zeitbereiche``: Tag für Regelarbeit/Pausen/Wege.
        self._monats_blatt_datum_override: dt.date | None = None
        self._periodisches_neuzeichnen = bool(periodisches_neuzeichnen)
        if self._periodisches_neuzeichnen:
            self._plant_naechstes_update()

    def _phasen_farben_aktuell(self) -> PhasenFarben:
        return self._phasen_farben_override or standard_phasen_farben()

    def darstellung_auffrischen(self) -> None:
        """Kalender neu zeichnen (z. B. nach Erscheinungsmodus-Wechsel)."""
        self._mehrtag_kopf_refresh()
        self._zeichnen()

    def _mehrtag_kopf_refresh(self) -> None:
        if self._mehrtag_kopf_label is None or self._mehrtag_kopfzeile_fn is None:
            return
        kf = kalender_farben()
        ist_heute = (
            self._mehrtag_heute_fn is not None
            and self._datum == self._mehrtag_heute_fn()
        )
        bg = kf.HINTERGRUND_ZEITLEISTE
        if self._mehrtag_kopf_rahmen is not None:
            self._mehrtag_kopf_rahmen.configure(bg=bg)
        if self._mehrtag_kopf_streifen_links is not None:
            self._mehrtag_kopf_streifen_links.configure(bg=bg)
        self._mehrtag_kopf_layout_update()
        self._mehrtag_kopf_label.configure(
            text=self._mehrtag_kopfzeile_fn(self._datum),
            bg=bg,
            fg=kf.JETZT_ZEIGER if ist_heute else kf.TEXT_ZEIT,
            font=("Segoe UI", 9, "bold") if ist_heute else ("Segoe UI", 9),
            cursor="hand2" if self._mehrtag_kopf_klick_einzel_tag is not None else "",
        )
        if self._mehrtag_kopf_klick_einzel_tag is None:
            self._mehrtag_kopf_label.unbind("<Enter>")
            self._mehrtag_kopf_label.unbind("<Leave>")

    def _mehrtag_kopf_hover_enter(self, _event: tk.Event | None = None) -> None:
        if self._mehrtag_kopf_label is None or self._mehrtag_kopf_klick_einzel_tag is None:
            return
        kf = kalender_farben()
        bg_h = hex_rgb_mit_faktor(
            kf.HINTERGRUND_ZEITLEISTE, MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR
        )
        self._mehrtag_kopf_label.configure(bg=bg_h)

    def _mehrtag_kopf_hover_leave(self, _event: tk.Event | None = None) -> None:
        self._mehrtag_kopf_refresh()

    def _bei_mehrtag_kopf_klick_einzel_tag(self, _event: tk.Event) -> None:
        if self._mehrtag_kopf_klick_einzel_tag is not None:
            self._mehrtag_kopf_klick_einzel_tag(self._datum)

    def _mehrtag_kopf_layout_update(self) -> None:
        if self._mehrtag_kopf_label is None:
            return
        kf = kalender_farben()
        if self._mehrtag_sep_links is not None:
            self._mehrtag_sep_links.configure(bg=kf.TRENNLINIE)
        if self._mehrtag_sep_zeitleiste is not None:
            self._mehrtag_sep_zeitleiste.configure(bg=kf.TRENNLINIE)
            try:
                self._mehrtag_sep_zeitleiste.place_configure(x=self._x_kalender_start())
            except tk.TclError:
                pass
        pad = 6
        if (
            self._mit_zeitleiste_und_sonne
            and self._kalenderblatt_zeigen
            and self._mehrtag_kopf_streifen_links is None
        ):
            pad = int(self._x_kalender_start()) + 6
        try:
            self._mehrtag_kopf_label.configure(padx=pad)
        except tk.TclError:
            pass

    def datum_setzen(self, neu: dt.date) -> None:
        """Anzuzeigenden Kalendertag setzen (Navigation)."""
        self._datum = neu
        if self._zoom is ZoomStufe.MITLAUF and not self._mitlauf_moeglich():
            self._zoom = ZoomStufe.GANZTAG
        self._mehrtag_kopf_refresh()
        self._zeichnen()

    def sonnenzeit_vorsaetze_setzen(self, sichtbar: bool) -> None:
        """Vorsätze (H·, T·, n↑, n↓, Auf-/Untergang) an den Sonnenzeitleisten-Marken."""
        self._mit_sonnenzeit_vorsaetzen = bool(sichtbar)
        self._zeichnen()

    @property
    def mit_sonnenzeit_vorsaetzen(self) -> bool:
        return self._mit_sonnenzeit_vorsaetzen

    def nautische_zeitleisten_setzen(self, sichtbar: bool) -> None:
        """Alias für :meth:`sonnenzeit_vorsaetze_setzen` (Rückwärtskompatibilität)."""
        self.sonnenzeit_vorsaetze_setzen(sichtbar)

    @property
    def mit_nautischen_zeitleisten(self) -> bool:
        """Entspricht :attr:`mit_sonnenzeit_vorsaetzen` (Rückwärtskompatibilität)."""
        return self._mit_sonnenzeit_vorsaetzen

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
        """Optionen für das Jetzt-Bannerschild (später aus Einstellungen)."""
        if bannerschild_anzeigen is not None:
            self._jetzt_bannerschild_anzeigen = bool(bannerschild_anzeigen)
        if wochentag is not None:
            self._jetzt_banner_wochentag = bool(wochentag)
        if tag is not None:
            self._jetzt_banner_tag = bool(tag)
        if monat is not None:
            self._jetzt_banner_monat = bool(monat)
        if jahr is not None:
            self._jetzt_banner_jahr = bool(jahr)
        if uhrzeit is not None:
            self._jetzt_banner_uhrzeit = bool(uhrzeit)
        self._zeichnen()

    @property
    def jetzt_bannerschild_anzeigen(self) -> bool:
        return self._jetzt_bannerschild_anzeigen

    @property
    def jetzt_banner_wochentag(self) -> bool:
        return self._jetzt_banner_wochentag

    @property
    def jetzt_banner_tag(self) -> bool:
        return self._jetzt_banner_tag

    @property
    def jetzt_banner_monat(self) -> bool:
        return self._jetzt_banner_monat

    @property
    def jetzt_banner_jahr(self) -> bool:
        return self._jetzt_banner_jahr

    @property
    def jetzt_banner_uhrzeit(self) -> bool:
        return self._jetzt_banner_uhrzeit

    @staticmethod
    def _iso_kalenderwoche(jetzt: dt.datetime) -> int:
        return jetzt.isocalendar()[1]

    def _jetzt_banner_text(
        self,
        jetzt: dt.datetime,
        *,
        kompakt_horizontal: bool | None = None,
    ) -> str:
        #: Nebeneinander mehrere Tage: kurzer Wochentag, Monat numerisch, Uhrzeit HH:MM.
        if kompakt_horizontal is None:
            kompakt_mehrere_horizontal = self._kalender_raster_modus in (
                KalenderRasterModus.DREI_TAGE_HORIZONTAL,
                KalenderRasterModus.WOCHENENDE_HORIZONTAL,
                KalenderRasterModus.WOCHE_HORIZONTAL,
                KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
            )
        else:
            kompakt_mehrere_horizontal = kompakt_horizontal
        teile: list[str] = []
        if self._jetzt_banner_wochentag:
            if kompakt_mehrere_horizontal:
                teile.append(
                    get_string(
                        f"kalender.wochentag_kurz.{jetzt.weekday()}",
                        self._locale,
                    )
                )
            else:
                teile.append(
                    get_string(
                        f"kalender.wochentag_lang.{jetzt.weekday()}",
                        self._locale,
                    )
                )
        if self._jetzt_banner_tag:
            t = str(jetzt.day)
            if resolve_locale(self._locale) == "de":
                t += "."
            teile.append(t)
        if self._jetzt_banner_monat:
            if kompakt_mehrere_horizontal:
                teile.append(str(jetzt.month))
            else:
                teile.append(
                    get_string(
                        f"kalender.monat_lang.{jetzt.month}",
                        self._locale,
                    )
                )
        if self._jetzt_banner_jahr:
            teile.append(str(jetzt.year))
        if (
            self._jetzt_banner_wochentag
            or self._jetzt_banner_tag
            or self._jetzt_banner_monat
            or self._jetzt_banner_jahr
            or self._jetzt_banner_uhrzeit
        ):
            kw = self._iso_kalenderwoche(jetzt)
            teile.append(
                f"{get_string('kalender.kw_prefix', self._locale)}{kw:02d}"
            )
        if self._jetzt_banner_uhrzeit:
            if kompakt_mehrere_horizontal:
                teile.append(jetzt.strftime("%H:%M"))
            else:
                teile.append(jetzt.strftime("%H:%M:%S"))
        return " ".join(teile)

    def _jetzt_banner_schrift_masse(self, text: str) -> tuple[int, int]:
        if self._jetzt_banner_font_tk is None:
            self._jetzt_banner_font_tk = tkfont.Font(
                root=self.winfo_toplevel(),
                family=self.JETZT_BANNER_FONT[0],
                size=self.JETZT_BANNER_FONT[1],
            )
        f = self._jetzt_banner_font_tk
        return (f.measure(text), int(f.metrics("linespace")))

    def _zeichnen_jetzt_zeiger(
        self,
        c: tk.Canvas,
        kf: KalenderFarbenPaket,
        x0: int,
        x_rechts: int,
        jetzt: dt.datetime,
        *,
        y_mitte: float | None = None,
        y_oben: float | None = None,
        kompakt_banner: bool | None = None,
        mit_bannerschild: bool | None = None,
    ) -> None:
        """Dünne Linie über das Kalenderblatt; optional Bannerschild nur textbreit ab ``x0``."""
        min_h = float(self.JETZT_ZEIGER_HOEHE)
        assert (y_mitte is not None) ^ (y_oben is not None)
        schild_an = (
            self._jetzt_bannerschild_anzeigen
            if mit_bannerschild is None
            else mit_bannerschild
        )
        text = ""
        if schild_an:
            text = self._jetzt_banner_text(
                jetzt, kompakt_horizontal=kompakt_banner
            )
        pad_x = self.JETZT_BANNER_PAD_X
        pad_y = self.JETZT_BANNER_PAD_Y
        tag = (self.JETZT_CANVAS_TAG,)

        if schild_an and text:
            tw, lh = self._jetzt_banner_schrift_masse(text)
            bar_h = max(min_h, float(lh) + 2.0 * pad_y)
            if y_mitte is not None:
                y1z = y_mitte - bar_h / 2.0
                y2z = y_mitte + bar_h / 2.0
                y_linie = float(y_mitte)
            else:
                y1z = float(y_oben)
                y2z = float(y_oben) + bar_h
                y_linie = (y1z + y2z) / 2.0
            c.create_line(
                x0,
                y_linie,
                x_rechts,
                y_linie,
                fill=kf.JETZT_ZEIGER,
                width=1,
                tags=tag,
            )
            x1b = float(x0)
            x2b = float(x0 + tw + 2 * pad_x)
            c.create_rectangle(
                x1b,
                y1z,
                x2b,
                y2z,
                outline=kf.JETZT_ZEIGER_RAND,
                fill=kf.JETZT_ZEIGER,
                width=1,
                tags=tag,
            )
            ty = (y1z + y2z) / 2.0
            c.create_text(
                x1b + float(pad_x),
                ty,
                anchor=tk.W,
                text=text,
                fill=kf.JETZT_BANNER_TEXT,
                font=self.JETZT_BANNER_FONT,
                tags=tag,
            )
            return

        if y_mitte is not None:
            y_linie = float(y_mitte)
        else:
            y_linie = float(y_oben) + min_h / 2.0
        c.create_line(
            x0,
            y_linie,
            x_rechts,
            y_linie,
            fill=kf.JETZT_ZEIGER,
            width=1,
            tags=tag,
        )

    def _jetzt_zeiger_nach_oben(self, c: tk.Canvas) -> None:
        try:
            c.tag_raise(self.JETZT_CANVAS_TAG)
        except tk.TclError:
            pass

    @property
    def datum(self) -> dt.date:
        return self._datum

    def _effektives_datum_fuer_zeichnung(self) -> dt.date:
        if self._monats_blatt_datum_override is not None:
            return self._monats_blatt_datum_override
        return self._datum

    @property
    def zoom(self) -> ZoomStufe:
        return self._zoom

    def zoom_sync_gruppe_setzen(
        self, gruppe: tuple["Tagesansicht", ...] | None
    ) -> None:
        """Gemeinsame Zoom-Stufe bei Klick (nur sinnvoll mit genau drei Ansichten)."""
        self._zoom_sync_gruppe = gruppe

    def _naechste_zoom_stufe(self) -> ZoomStufe:
        reihenfolge = (
            ZoomStufe.GANZTAG,
            ZoomStufe.WACHZEIT,
            ZoomStufe.MITLAUF,
        )
        i = reihenfolge.index(self._zoom)
        naechste = reihenfolge[(i + 1) % 3]
        if naechste is ZoomStufe.MITLAUF and not self._mitlauf_moeglich():
            naechste = ZoomStufe.GANZTAG
        return naechste

    def _mitlauf_moeglich(self) -> bool:
        return self._datum == self._heute_im_standort()

    def _heute_im_standort(self) -> dt.date:
        """Kalendertag in der Standort-Zeitzone (nicht ``date.today()`` / OS-Zeitzone)."""
        return dt.datetime.now(self._standort_tz).date()

    def _minuten_seit_anzeige_mitternacht(self, jetzt: dt.datetime) -> float:
        """Minuten seit lokaler Mitternacht des angezeigten :attr:`datum`."""
        mitternacht = dt.datetime.combine(
            self._datum, dt.time(0, 0), tzinfo=self._standort_tz
        )
        return (jetzt - mitternacht).total_seconds() / 60.0

    def _sichtbarer_minutenbereich(self) -> tuple[float, float]:
        if self._sichtbar_cache is not None:
            return self._sichtbar_cache
        return self._sichtbarer_minutenbereich_berechnen()

    def _sichtbarer_minutenbereich_berechnen(self) -> tuple[float, float]:
        """Sichtbarer Minutenbereich; bei „heute“ untere Kante ggf. über 24:00 hinaus (Jetzt-Zeiger)."""
        if not self._kalenderblatt_zeigen:
            #: Monatsstreifen: Oberkante = 00:00, Unterkante = 24:00 (kein Zusatzbereich für „heute“).
            return (0.0, 24.0 * 60.0)
        jetzt = dt.datetime.now(self._standort_tz)
        hl = jetzt.date()
        if self._zoom is ZoomStufe.GANZTAG:
            lo, hi = 0.0, 24.0 * 60.0
            if self._datum == hl:
                m = self._minuten_seit_anzeige_mitternacht(jetzt)
                hi = max(hi, m + 60.0)
            return (lo, hi)
        a = float(self._wachzeit.start_minuten_seit_mitternacht)
        b = float(self._wachzeit.ende_minuten_seit_mitternacht)
        if a >= b:
            lo, hi = 0.0, 24.0 * 60.0
            if self._datum == hl:
                m = self._minuten_seit_anzeige_mitternacht(jetzt)
                hi = max(hi, m + 60.0)
            return (lo, hi)
        lo, hi = a, b
        if self._datum == hl:
            m = self._minuten_seit_anzeige_mitternacht(jetzt)
            if lo <= m <= hi:
                hi = max(hi, m + 60.0)
        return (lo, hi)

    def _minute_nach_y(self, minute: float, h_innen: float, y0: float) -> float:
        start, ende = self._sichtbarer_minutenbereich()
        span = ende - start
        if span <= 0:
            return y0
        t = (minute - start) / span
        return y0 + t * h_innen

    def _x_kalender_start(self) -> int:
        if not self._mit_zeitleiste_und_sonne:
            return 0
        return self.ZEITLEISTE_TEXT_BREITE + (
            self.SONNENSPALT_BREITE if self._mit_sonnenspalte else 0
        )

    def _x_zeitleiste_sonnenmarken(self, x_text: int) -> int:
        return x_text - self.ZEITLEISTE_SONNENMARKEN_RAND

    @property
    def _standort_tz(self) -> ZoneInfo:
        return ZoneInfo(self._standort.zeitzone)

    def _datetime_standort(self, d: dt.date, tm: dt.time) -> dt.datetime:
        return dt.datetime.combine(d, tm, tzinfo=self._standort_tz)

    def _minute_seit_mitternacht_von_dt(self, t: dt.datetime) -> float:
        return (
            t.hour * 60
            + t.minute
            + (t.second + t.microsecond / 1_000_000) / 60.0
        )

    def _zeichnen_mondphase_bei_unterkulmination(
        self,
        c: tk.Canvas,
        x_text: int,
        y_zeit_mitte: float,
        y_clip_oben: float,
        y_clip_unten: float,
        tev_unter: dt.datetime,
    ) -> None:
        """Mond zuerst, Uhrzeit danach; Mittelpunkt der Scheibe an der Textmitte (überdeckend)."""
        if not self._mit_sonnenspalte:
            return
        r = float(self.MONDRADIUS)
        cx = float(
            self._x_zeitleiste_sonnenmarken(x_text)
            - self.MOND_CX_LINKS_VON_SONNENMARKE
        )
        cy = float(y_zeit_mitte + self.MOND_UNTER_KULMINATION_OFFSET_Y)
        if cy - r < y_clip_oben + 1 or cy + r > y_clip_unten - 1:
            return
        phase = mondphase_synode_anteil(tev_unter.date())
        mondscheibe_zeichnen(c, cx, cy, r, phase)

    def _zeichnen_sonne_bei_oberkulmination(
        self,
        c: tk.Canvas,
        x_text: int,
        y_zeit_mitte: float,
        y_clip_oben: float,
        y_clip_unten: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        """Sonne hinter der Uhrzeit des Sonnenhöchststands (Oberkulmination)."""
        if not self._mit_sonnenspalte:
            return
        r = float(self.SONNENRADIUS)
        extra = float(self.SONN_STRAHL_CLIP_EXTRA)
        cx = float(
            self._x_zeitleiste_sonnenmarken(x_text)
            - self.SONN_CX_LINKS_VON_SONNENMARKE
        )
        cy = float(y_zeit_mitte + self.SONN_OBER_KULMINATION_OFFSET_Y)
        if cy - r - extra < y_clip_oben + 1 or cy + r + extra > y_clip_unten - 1:
            return
        sonne_zeitleiste_zeichnen(
            c,
            cx,
            cy,
            r,
            fuell=kf.ICON_SONNE_FLAECE,
            strahl=kf.ICON_SONNE_STRAHL,
        )

    def _zeichnen_zeitleisten_text_mit_rand(
        self,
        c: tk.Canvas,
        x: float,
        y: float,
        anchor: str,
        text: str,
        font: tuple[str, int] | tuple[str, int, str],
        fuell: str,
        rand: str,
    ) -> None:
        """Text mit 1px-Umriss (8 Nachbarn), für Lesbarkeit auf hell und dunkel."""
        for dx, dy in (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        ):
            c.create_text(
                x + dx,
                y + dy,
                anchor=anchor,
                text=text,
                fill=rand,
                font=font,
            )
        c.create_text(
            x, y, anchor=anchor, text=text, fill=fuell, font=font
        )

    def _text_zeitleisten_marke(
        self, t: dt.datetime, prefix_schluessel: str
    ) -> str:
        """Nur Uhrzeit, oder mit Locale-Vorsatz wenn ``mit_sonnenzeit_vorsaetzen``."""
        if self._mit_sonnenzeit_vorsaetzen:
            p = get_string(prefix_schluessel, self._locale)
            if p:
                return f"{p}{t.strftime('%H:%M')}"
        return t.strftime("%H:%M")

    def _zeichnen_kulmination_zeiten_statisch(
        self,
        c: tk.Canvas,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        k = sonnen_kulmination_am_tag(self._datum, self._standort)
        if k is None:
            return
        start_m, ende_m = self._sichtbarer_minutenbereich()
        font = ("Segoe UI", 7)
        for ober, tev in ((True, k.oberkulmination), (False, k.unterkulmination)):
            if tev.date() != self._datum:
                continue
            m = self._minute_seit_mitternacht_von_dt(tev)
            if not (start_m <= m <= ende_m):
                continue
            y = self._minute_nach_y(m, h_innen, y0)
            if y < y0 or y > y1:
                continue
            if ober:
                self._zeichnen_sonne_bei_oberkulmination(
                    c, x_text, y, y0, y1, kf
                )
            else:
                self._zeichnen_mondphase_bei_unterkulmination(
                    c, x_text, y, y0, y1, tev
                )
            label = self._text_zeitleisten_marke(
                tev,
                (
                    "kalender.kulmination_oben_prefix"
                    if ober
                    else "kalender.kulmination_unten_prefix"
                ),
            )
            xa = float(self._x_zeitleiste_sonnenmarken(x_text))
            if ober:
                c.create_text(
                    xa,
                    y,
                    anchor=tk.E,
                    text=label,
                    fill=kf.TEXT_ZEIT,
                    font=font,
                )
            else:
                self._zeichnen_zeitleisten_text_mit_rand(
                    c,
                    xa,
                    float(y),
                    tk.E,
                    label,
                    font,
                    kf.TEXT_UNTERKULMINATION,
                    kf.TEXT_UNTERKULMINATION_RAND,
                )

    def _zeichnen_zeitumstellung_statisch(
        self,
        c: tk.Canvas,
        x0: int,
        x_rechts: int,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        u = umstellung_am_tag(self._datum, self._standort.zeitzone)
        if u is None or u.zeitpunkt.date() != self._datum:
            return
        start_m, ende_m = self._sichtbarer_minutenbereich()
        m = self._minute_seit_mitternacht_von_dt(u.zeitpunkt)
        if not (start_m <= m <= ende_m):
            return
        y = self._minute_nach_y(m, h_innen, y0)
        if y < y0 or y > y1:
            return
        c.create_line(
            x0,
            y,
            x_rechts,
            y,
            fill=kf.ZEITUMSTELLUNG_LINIE,
            width=1,
            dash=(4, 4),
        )
        if not self._mit_zeitleiste_und_sonne:
            return
        schluessel = (
            "kalender.zeitumstellung_sommerzeit_prefix"
            if u.art is ZeitumstellungArt.SOMMERZEIT_BEGINN
            else "kalender.zeitumstellung_winterzeit_prefix"
        )
        font = ("Segoe UI", 7)
        c.create_text(
            float(self._x_zeitleiste_sonnenmarken(x_text)),
            y,
            anchor=tk.E,
            text=self._text_zeitleisten_marke(u.zeitpunkt, schluessel),
            fill=kf.TEXT_ZEIT,
            font=font,
        )

    def _zeichnen_kulmination_zeiten_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        font = ("Segoe UI", 7)
        d = t_top.date()
        ende_tag = t_bot.date()
        while d <= ende_tag:
            k = sonnen_kulmination_am_tag(d, self._standort)
            if k is not None:
                for ober, tev in ((True, k.oberkulmination), (False, k.unterkulmination)):
                    if not (t_top <= tev <= t_bot):
                        continue
                    y = self._dt_nach_y_mitlauf(tev, t_top, h_innen, y0)
                    if y < y0 or y > y1:
                        continue
                    if ober:
                        self._zeichnen_sonne_bei_oberkulmination(
                            c, x_text, y, y0, y1, kf
                        )
                    else:
                        self._zeichnen_mondphase_bei_unterkulmination(
                            c, x_text, y, y0, y1, tev
                        )
                    label = self._text_zeitleisten_marke(
                        tev,
                        (
                            "kalender.kulmination_oben_prefix"
                            if ober
                            else "kalender.kulmination_unten_prefix"
                        ),
                    )
                    xa = float(self._x_zeitleiste_sonnenmarken(x_text))
                    if ober:
                        c.create_text(
                            xa,
                            y,
                            anchor=tk.E,
                            text=label,
                            fill=kf.TEXT_ZEIT,
                            font=font,
                        )
                    else:
                        self._zeichnen_zeitleisten_text_mit_rand(
                            c,
                            xa,
                            float(y),
                            tk.E,
                            label,
                            font,
                            kf.TEXT_UNTERKULMINATION,
                            kf.TEXT_UNTERKULMINATION_RAND,
                        )
            d += dt.timedelta(days=1)

    def _zeichnen_zeitumstellung_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x0: int,
        x_rechts: int,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        font = ("Segoe UI", 7)
        d = t_top.date()
        ende_tag = t_bot.date()
        while d <= ende_tag:
            u = umstellung_am_tag(d, self._standort.zeitzone)
            if u is not None and t_top <= u.zeitpunkt <= t_bot:
                y = self._dt_nach_y_mitlauf(u.zeitpunkt, t_top, h_innen, y0)
                if y0 <= y <= y1:
                    c.create_line(
                        x0,
                        y,
                        x_rechts,
                        y,
                        fill=kf.ZEITUMSTELLUNG_LINIE,
                        width=1,
                        dash=(4, 4),
                    )
                    if self._mit_zeitleiste_und_sonne:
                        schluessel = (
                            "kalender.zeitumstellung_sommerzeit_prefix"
                            if u.art is ZeitumstellungArt.SOMMERZEIT_BEGINN
                            else "kalender.zeitumstellung_winterzeit_prefix"
                        )
                        c.create_text(
                            float(self._x_zeitleiste_sonnenmarken(x_text)),
                            y,
                            anchor=tk.E,
                            text=self._text_zeitleisten_marke(
                                u.zeitpunkt, schluessel
                            ),
                            fill=kf.TEXT_ZEIT,
                            font=font,
                        )
            d += dt.timedelta(days=1)

    def _zeichnen_sonnenauf_untergang_statisch(
        self,
        c: tk.Canvas,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        #: Horizont 0°: bei Woche übereinander und Monatsstreifen ohne Uhrzeit-Text (nur Grafik).
        if self._kalender_raster_modus is KalenderRasterModus.WOCHE_VERTIKAL:
            return
        if not self._kalenderblatt_zeigen:
            return
        z = sonnenzeiten_am_tag(self._datum, self._standort)
        if z is None:
            return
        start_m, ende_m = self._sichtbarer_minutenbereich()
        font = ("Segoe UI", 7)
        for aufgang, tev in ((True, z.sonnenaufgang), (False, z.sonnenuntergang)):
            if tev.date() != self._datum:
                continue
            m = self._minute_seit_mitternacht_von_dt(tev)
            if not (start_m <= m <= ende_m):
                continue
            y = self._minute_nach_y(m, h_innen, y0)
            if y < y0 or y > y1:
                continue
            schluessel = (
                "kalender.sonnenaufgang_prefix"
                if aufgang
                else "kalender.sonnenuntergang_prefix"
            )
            c.create_text(
                self._x_zeitleiste_sonnenmarken(x_text),
                y,
                anchor=tk.E,
                text=self._text_zeitleisten_marke(tev, schluessel),
                fill=kf.TEXT_ZEIT,
                font=font,
            )

    def _zeichnen_sonnenauf_untergang_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        if self._kalender_raster_modus is KalenderRasterModus.WOCHE_VERTIKAL:
            return
        if not self._kalenderblatt_zeigen:
            return
        font = ("Segoe UI", 7)
        d = t_top.date()
        ende_tag = t_bot.date()
        while d <= ende_tag:
            z = sonnenzeiten_am_tag(d, self._standort)
            if z is not None:
                for aufgang, tev in (
                    (True, z.sonnenaufgang),
                    (False, z.sonnenuntergang),
                ):
                    if not (t_top <= tev <= t_bot):
                        continue
                    y = self._dt_nach_y_mitlauf(tev, t_top, h_innen, y0)
                    if y < y0 or y > y1:
                        continue
                    schluessel = (
                        "kalender.sonnenaufgang_prefix"
                        if aufgang
                        else "kalender.sonnenuntergang_prefix"
                    )
                    c.create_text(
                        self._x_zeitleiste_sonnenmarken(x_text),
                        y,
                        anchor=tk.E,
                        text=self._text_zeitleisten_marke(tev, schluessel),
                        fill=kf.TEXT_ZEIT,
                        font=font,
                    )
            d += dt.timedelta(days=1)

    def _zeichnen_nautische_zeiten_statisch(
        self,
        c: tk.Canvas,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        n = nautische_daemmerung_am_tag(self._datum, self._standort)
        if n is None:
            return
        start_m, ende_m = self._sichtbarer_minutenbereich()
        font = ("Segoe UI", 7)
        for morgens, tev in ((True, n.morgens), (False, n.abends)):
            if tev.date() != self._datum:
                continue
            m = self._minute_seit_mitternacht_von_dt(tev)
            if not (start_m <= m <= ende_m):
                continue
            y = self._minute_nach_y(m, h_innen, y0)
            if y < y0 or y > y1:
                continue
            c.create_text(
                self._x_zeitleiste_sonnenmarken(x_text),
                y,
                anchor=tk.E,
                text=self._text_zeitleisten_marke(
                    tev,
                    (
                        "kalender.naut_morgen_prefix"
                        if morgens
                        else "kalender.naut_abend_prefix"
                    ),
                ),
                fill=kf.TEXT_ZEIT,
                font=font,
            )

    def _zeichnen_nautische_zeiten_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_text: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        if not self._mit_sonnenspalte:
            return
        font = ("Segoe UI", 7)
        d = t_top.date()
        ende_tag = t_bot.date()
        while d <= ende_tag:
            n = nautische_daemmerung_am_tag(d, self._standort)
            if n is not None:
                for morgens, tev in ((True, n.morgens), (False, n.abends)):
                    if not (t_top <= tev <= t_bot):
                        continue
                    y = self._dt_nach_y_mitlauf(tev, t_top, h_innen, y0)
                    if y < y0 or y > y1:
                        continue
                    c.create_text(
                        self._x_zeitleiste_sonnenmarken(x_text),
                        y,
                        anchor=tk.E,
                        text=self._text_zeitleisten_marke(
                            tev,
                            (
                                "kalender.naut_morgen_prefix"
                                if morgens
                                else "kalender.naut_abend_prefix"
                            ),
                        ),
                        fill=kf.TEXT_ZEIT,
                        font=font,
                    )
            d += dt.timedelta(days=1)

    def _minute_aus_y(self, y: float, h_innen: float, y0: float) -> float:
        vis_lo, vis_hi = self._sichtbarer_minutenbereich()
        span = vis_hi - vis_lo
        if span <= 0:
            return vis_lo
        t = (y - y0) / h_innen
        return vis_lo + t * span

    def _datetime_aus_y_mitlauf(
        self, y: float, t_top: dt.datetime, h_innen: float, y0: float
    ) -> dt.datetime:
        span = self.MITLAUF_SPANNE_STUNDEN * 3600.0
        if span <= 0:
            return t_top
        rel = ((y - y0) / h_innen) * span
        return t_top + dt.timedelta(seconds=rel)

    def _zeichnen_sonnenspalte_statisch(
        self,
        c: tk.Canvas,
        x_links: int,
        x_rechts: int,
        y0: float,
        y1: float,
        h_innen: float,
    ) -> None:
        zeiten = sonnenzeiten_am_tag(self._datum, self._standort)
        n = max(1, int(h_innen))
        for i in range(n):
            y_top = y0 + (i / n) * h_innen
            y_bot = y0 + ((i + 1) / n) * h_innen
            mitte_min = self._minute_aus_y((y_top + y_bot) / 2.0, h_innen, y0)
            if zeiten is None:
                farbe = "#000000"
            else:
                t = datetime_aus_datum_und_minute_float(
                    self._datum,
                    mitte_min,
                    self._standort.zeitzone,
                )
                h = helligkeit_01(t, zeiten)
                farbe = farbe_sonnenstreifen(h)
            c.create_rectangle(
                x_links,
                y_top,
                x_rechts,
                y_bot,
                fill=farbe,
                width=0,
            )

    def _zeichnen_sonnenspalte_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        x_links: int,
        x_rechts: int,
        y0: float,
        h_innen: float,
    ) -> None:
        n = max(1, int(h_innen))
        for i in range(n):
            y_top = y0 + (i / n) * h_innen
            y_bot = y0 + ((i + 1) / n) * h_innen
            t = self._datetime_aus_y_mitlauf(
                (y_top + y_bot) / 2.0,
                t_top,
                h_innen,
                y0,
            )
            tag = t.date()
            zeiten = sonnenzeiten_am_tag(tag, self._standort)
            if zeiten is None:
                farbe = "#000000"
            else:
                h = helligkeit_01(t, zeiten)
                farbe = farbe_sonnenstreifen(h)
            c.create_rectangle(
                x_links,
                y_top,
                x_rechts,
                y_bot,
                fill=farbe,
                width=0,
            )

    def _ist_wach_minute_seit_mitternacht(self, minute: float) -> bool:
        w_lo = float(self._wachzeit.start_minuten_seit_mitternacht)
        w_hi = float(self._wachzeit.ende_minuten_seit_mitternacht)
        return w_lo <= minute < w_hi

    def _ist_wach_datetime(self, t: dt.datetime) -> bool:
        m = t.hour * 60 + t.minute + (t.second + t.microsecond / 1_000_000) / 60.0
        return self._ist_wach_minute_seit_mitternacht(m)

    def _phasen_segmente_sichtbar(self) -> list[tuple[float, float, bool]]:
        """(minute_von, minute_bis, ist_wach) im aktuell sichtbaren Minutenbereich."""
        vis_lo, vis_hi = self._sichtbarer_minutenbereich()
        w_lo = float(self._wachzeit.start_minuten_seit_mitternacht)
        w_hi = float(self._wachzeit.ende_minuten_seit_mitternacht)
        seg: list[tuple[float, float, bool]] = []
        t = vis_lo
        eps = 1e-6
        while t < vis_hi - eps:
            if t < w_lo:
                end = min(vis_hi, w_lo)
                seg.append((t, end, False))
                t = end
            elif t < w_hi:
                end = min(vis_hi, w_hi)
                seg.append((t, end, True))
                t = end
            else:
                seg.append((t, vis_hi, False))
                t = vis_hi
        return seg

    def _phasen_split_datetime(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[dt.datetime]:
        pts: set[dt.datetime] = {t_top, t_bot}
        d = t_top.date()
        limit = t_bot.date()
        while d <= limit:
            for hh, mm in ((6, 30), (22, 30)):
                tx = self._datetime_standort(d, dt.time(hh, mm))
                if t_top < tx < t_bot:
                    pts.add(tx)
            d += dt.timedelta(days=1)
        return sorted(pts)

    def _phasen_segmente_mitlauf(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[tuple[dt.datetime, dt.datetime, bool]]:
        grenzen = self._phasen_split_datetime(t_top, t_bot)
        out: list[tuple[dt.datetime, dt.datetime, bool]] = []
        for i in range(len(grenzen) - 1):
            a, b = grenzen[i], grenzen[i + 1]
            if a >= b:
                continue
            mitte = a + (b - a) / 2
            out.append((a, b, self._ist_wach_datetime(mitte)))
        return out

    def _dt_nach_y_mitlauf(
        self, t: dt.datetime, t_top: dt.datetime, h_innen: float, y0: float
    ) -> float:
        span = self.MITLAUF_SPANNE_STUNDEN * 3600.0
        if span <= 0:
            return y0
        sek = (t - t_top).total_seconds()
        return y0 + sek / span * h_innen

    def _stunden_marken_mitlauf(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[dt.datetime]:
        step = self._stunden_raster_intervall
        marken: list[dt.datetime] = []
        t = t_top.replace(minute=0, second=0, microsecond=0)
        if t <= t_top:
            t += dt.timedelta(hours=1)
        while t < t_bot and t.hour % step != 0:
            t += dt.timedelta(hours=1)
        while t < t_bot:
            marken.append(t)
            t += dt.timedelta(hours=step)
        return marken

    def _format_zeit_mitlauf(self, t: dt.datetime) -> str:
        return t.strftime("%H:%M")

    def _mitlauf_mitternaechte_im_fenster(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[dt.datetime]:
        """Lokale Mitternächte mit ``t_top < m < t_bot`` (Tagesgrenzen im Mitlauf)."""
        tz = t_top.tzinfo
        m = dt.datetime.combine(t_top.date(), dt.time.min, tzinfo=tz)
        if m <= t_top:
            m += dt.timedelta(days=1)
        out: list[dt.datetime] = []
        while m < t_bot:
            out.append(m)
            m += dt.timedelta(days=1)
        return out

    def _zeichnen_wochen_tag_trennung(
        self,
        c: tk.Canvas,
        w: float,
        h: float,
        xk: float,
        x_rechts: float,
        y0: float,
        y1: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        """Taggrenze: senkrechte Linie links (nebeneinander) bzw. waagrechte oben (übereinander)."""
        farbe = kf.TRENNLINIE
        if self._woche_tag_trennung_links:
            c.create_line(0, y0, 0, y1, fill=farbe, width=1)
        if self._woche_tag_trennung_oben:
            c.create_line(xk, y0, x_rechts, y0, fill=farbe, width=1)

    def _zeichnen_vertikale_dreier_tagestrennung(
        self,
        c: tk.Canvas,
        x_kalender_links: float,
        x_rechts: float,
        y1: float,
    ) -> None:
        """Unter dem sichtbaren Tag: schwarze Linie nur auf dem Kalenderblatt (3× übereinander, statisch)."""
        if self._kalender_raster_modus not in (
            KalenderRasterModus.DREI_TAGE_VERTIKAL,
            KalenderRasterModus.WOCHENENDE_VERTIKAL,
            KalenderRasterModus.WOCHE_VERTIKAL,
            KalenderRasterModus.ARBEITSWOCHE_VERTIKAL,
        ):
            return
        c.create_line(
            x_kalender_links,
            y1,
            x_rechts,
            y1,
            fill=self.MITLAUF_TAGWECHSEL_SCHWARZ,
            width=2,
        )

    def _zeichnen_mitlauf_tageswechsel(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_kalender_links: int,
        x_rechts: int,
        y0: float,
        y1: float,
        h_innen: float,
        kf: KalenderFarbenPaket,
    ) -> None:
        """3 px hoch: grau–schwarz–grau nur über das Kalenderblatt (nicht Zeitleiste/Sonnenspalte)."""
        grau = kf.HINTERGRUND_ZEITLEISTE
        schwarz = self.MITLAUF_TAGWECHSEL_SCHWARZ
        x1, x2 = x_kalender_links, x_rechts
        for mitternacht in self._mitlauf_mitternaechte_im_fenster(t_top, t_bot):
            y = self._dt_nach_y_mitlauf(mitternacht, t_top, h_innen, y0)
            yi = int(round(y))
            fills = (grau, schwarz, grau)
            for i, fill in enumerate(fills):
                ya = float(yi - 1 + i)
                yb = ya + 1.0
                if yb <= y0 or ya >= y1:
                    continue
                c.create_rectangle(
                    x1,
                    max(ya, y0),
                    x2,
                    min(yb, y1),
                    fill=fill,
                    width=0,
                )

    def _arbeit_segmente_mitlauf(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[tuple[dt.datetime, dt.datetime]]:
        out: list[tuple[dt.datetime, dt.datetime]] = []
        d = t_top.date()
        limit = t_bot.date()
        while d <= limit:
            arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(d)
            if arbeitszeit is not None:
                start_m, ende_m = arbeitszeit
                sh, sm = divmod(start_m, 60)
                eh, em = divmod(ende_m, 60)
                ta = self._datetime_standort(d, dt.time(sh, sm))
                tb = self._datetime_standort(d, dt.time(eh, em))
                a = max(ta, t_top)
                b = min(tb, t_bot)
                if a < b:
                    out.append((a, b))
            d += dt.timedelta(days=1)
        return out

    def _arbeitszeit_fuer_tag_ohne_krankmeldung(
        self, tag: dt.date
    ) -> tuple[int, int] | None:
        if ist_krankgeschrieben_am(tag):
            return None
        return self._regelarbeit.arbeitszeit_fuer_tag(tag)

    @staticmethod
    def _krank_tooltip_text_fuer_tag(tag: dt.date) -> str | None:
        eintrag = eintrag_fuer_tag(tag)
        if eintrag is None:
            return None
        art = "Wiedervorstellung" if eintrag.arzttermin_art == "wiedervorstellung" else "Nachkontrolle"
        arzt_name = eintrag.arzt_name_snapshot or "Arzt nicht hinterlegt"
        return (
            "Arbeitsunfaehigkeit\n"
            f"von {eintrag.start_datum.strftime('%d.%m.%Y')}\n"
            f"bis {eintrag.ende_datum.strftime('%d.%m.%Y')}\n"
            f"{art}: {eintrag.wiedervorstellung_datum.strftime('%d.%m.%Y')} {eintrag.arzttermin_zeit}\n"
            f"{arzt_name}"
        )

    def _krank_tag_und_text_unter_koordinate(
        self, x: float, y: float
    ) -> tuple[dt.date, str] | None:
        if not self._kalenderblatt_zeigen:
            return None
        w = max(self._canvas.winfo_width(), 2)
        h = max(self._canvas.winfo_height(), 2)
        xk = self._x_kalender_start()
        x_rechts = w - self._rand_rechts
        y0 = float(self.RAND_OBEN)
        y1 = float(h) - float(self._rand_unten)
        if y < y0 or y > y1 or x < xk or x > x_rechts:
            return None
        h_innen = max(y1 - y0, 1.0)
        if self._zoom is ZoomStufe.MITLAUF and self._mitlauf_moeglich():
            tz = ZoneInfo(self._standort.zeitzone)
            t_top = dt.datetime.now(tz).replace(microsecond=0)
            tag = self._datetime_aus_y_mitlauf(y, t_top, h_innen, y0).date()
        else:
            tag = self._effektives_datum_fuer_zeichnung()
        text = self._krank_tooltip_text_fuer_tag(tag)
        if text is None:
            return None
        marker_breite = min(xk + self.KRANKRAND_BREITE + 4.0, x_rechts)
        if x <= marker_breite:
            return (tag, text)
        if ist_wiedervorstellung_am(tag):
            radius = 11.0
            cx = min(x_rechts - radius - 4.0, xk + 22.0)
            if self._zoom is ZoomStufe.MITLAUF and self._mitlauf_moeglich():
                marker_y = self._dt_nach_y_mitlauf(
                    dt.datetime.combine(tag, dt.time(9, 0), tzinfo=t_top.tzinfo),
                    t_top,
                    h_innen,
                    y0,
                )
            else:
                marker_y = y0 + radius + 4.0
            if (x - cx) ** 2 + (y - marker_y) ** 2 <= radius**2:
                return (tag, text)
        return None

    def _krank_tooltip_anzeigen(self, text: str, root_x: int, root_y: int) -> None:
        if self._krank_tooltip is not None and self._krank_tooltip_text == text:
            try:
                self._krank_tooltip.wm_geometry(f"+{root_x + 12}+{root_y + 12}")
            except tk.TclError:
                pass
            return
        self._krank_tooltip_verstecken()
        self._krank_tooltip_text = text
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{root_x + 12}+{root_y + 12}")
        kf = kalender_farben()
        rahmen = tk.Frame(tip, bg=self.KRANKRAND_AKZENT, bd=0, highlightthickness=0)
        rahmen.pack()
        tk.Label(
            rahmen,
            text=text,
            bg=self.KRANKRAND_AKZENT,
            fg="#1F1F1F",
            justify=tk.LEFT,
            anchor=tk.W,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        ).pack()
        self._krank_tooltip = tip

    def _krank_tooltip_verstecken(self) -> None:
        if self._krank_tooltip is not None:
            try:
                self._krank_tooltip.destroy()
            except tk.TclError:
                pass
        self._krank_tooltip = None
        self._krank_tooltip_text = None

    def _bei_maus_bewegung(self, event: tk.Event) -> None:
        hit = self._krank_tag_und_text_unter_koordinate(float(event.x), float(event.y))
        if hit is None:
            self._krank_tooltip_verstecken()
            self._canvas.configure(cursor="")
            return
        _, text = hit
        self._canvas.configure(cursor="hand2")
        self._krank_tooltip_anzeigen(text, int(event.x_root), int(event.y_root))

    def _bei_maus_verlassen(self, _event: tk.Event | None = None) -> None:
        self._canvas.configure(cursor="")
        self._krank_tooltip_verstecken()

    def _zeichnen_krankstatus_statisch(
        self,
        c: tk.Canvas,
        tag: dt.date,
        x_links: float,
        x_rechts: float,
        y0: float,
        y1: float,
    ) -> None:
        if ist_krankgeschrieben_am(tag):
            c.create_rectangle(
                x_links,
                y0,
                min(x_links + self.KRANKRAND_BREITE, x_rechts),
                y1,
                fill=self.KRANKRAND_FARBE,
                width=0,
            )
            c.create_rectangle(
                x_links,
                y0,
                min(x_links + 3, x_rechts),
                y1,
                fill=self.KRANKRAND_AKZENT,
                width=0,
            )
        if ist_wiedervorstellung_am(tag):
            radius = 9.0
            cx = min(x_rechts - radius - 4.0, x_links + 22.0)
            cy = y0 + radius + 4.0
            c.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=self.ARZT_MARKER_FARBE,
                outline=self.ARZT_MARKER_FARBE,
                width=1,
            )
            c.create_text(
                cx,
                cy,
                text=self.ARZT_MARKER_TEXT,
                fill="#FFFFFF",
                font=("Segoe UI", 8, "bold"),
            )

    def _zeichnen_krankstatus_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        d = t_top.date()
        limit = t_bot.date()
        while d <= limit:
            tag_start = self._datetime_standort(d, dt.time(0, 0))
            tag_ende = tag_start + dt.timedelta(days=1)
            a = max(tag_start, t_top)
            b = min(tag_ende, t_bot)
            if a < b and ist_krankgeschrieben_am(d):
                ya = self._dt_nach_y_mitlauf(a, t_top, h_innen, y0)
                yb = self._dt_nach_y_mitlauf(b, t_top, h_innen, y0)
                c.create_rectangle(
                    x_links,
                    ya,
                    min(x_links + self.KRANKRAND_BREITE, x_rechts),
                    yb,
                    fill=self.KRANKRAND_FARBE,
                    width=0,
                )
                c.create_rectangle(
                    x_links,
                    ya,
                    min(x_links + 3, x_rechts),
                    yb,
                    fill=self.KRANKRAND_AKZENT,
                    width=0,
                )
            if ist_wiedervorstellung_am(d):
                marker_dt = max(a, min(b, tag_start + dt.timedelta(hours=9)))
                ym = self._dt_nach_y_mitlauf(marker_dt, t_top, h_innen, y0)
                radius = 9.0
                cx = min(x_rechts - radius - 4.0, x_links + 22.0)
                c.create_oval(
                    cx - radius,
                    ym - radius,
                    cx + radius,
                    ym + radius,
                    fill=self.ARZT_MARKER_FARBE,
                    outline=self.ARZT_MARKER_FARBE,
                    width=1,
                )
                c.create_text(
                    cx,
                    ym,
                    text=self.ARZT_MARKER_TEXT,
                    fill="#FFFFFF",
                    font=("Segoe UI", 8, "bold"),
                )
            d += dt.timedelta(days=1)

    def _zeichnen_regelarbeit_statisch(
        self,
        c: tk.Canvas,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        p = self._regelarbeit
        arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(
            self._effektives_datum_fuer_zeichnung()
        )
        if arbeitszeit is None:
            return
        w_lo = float(arbeitszeit[0])
        w_hi = float(arbeitszeit[1])
        vis_lo, vis_hi = self._sichtbarer_minutenbereich()
        lo = max(vis_lo, w_lo)
        hi = min(vis_hi, w_hi)
        if lo >= hi:
            return
        fill = p.arbeitsflaechen_farbe_hex()
        ya = self._minute_nach_y(lo, h_innen, y0)
        yb = self._minute_nach_y(hi, h_innen, y0)
        if yb < ya:
            ya, yb = yb, ya
        if yb - ya < 1.0:
            yb = ya + 1.0
        c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0)

    def _zeichnen_regelarbeit_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        fill = self._regelarbeit.arbeitsflaechen_farbe_hex()
        for ta, tb in self._arbeit_segmente_mitlauf(t_top, t_bot):
            ya = self._dt_nach_y_mitlauf(ta, t_top, h_innen, y0)
            yb = self._dt_nach_y_mitlauf(tb, t_top, h_innen, y0)
            if yb < ya:
                ya, yb = yb, ya
            if yb - ya < 1.0:
                yb = ya + 1.0
            c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0)

    def _zeichnen_pausen_statisch(
        self,
        c: tk.Canvas,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        pr = self._pausenprofil
        tag = self._effektives_datum_fuer_zeichnung()
        bloecke = pr.bloecke_fuer_wochentag(tag.weekday())
        if not bloecke:
            return
        arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(tag)
        if arbeitszeit is None:
            return
        fill = pr.pauseflaechen_farbe_hex()
        w_lo = float(arbeitszeit[0])
        w_hi = float(arbeitszeit[1])
        for b in bloecke:
            b_lo = float(b.start_minuten_seit_mitternacht)
            b_hi = float(b.ende_minuten_seit_mitternacht)
            lo = max(b_lo, w_lo)
            hi = min(b_hi, w_hi)
            if lo >= hi:
                continue
            self._rechteck_minuten_statisch(c, lo, hi, x_links, x_rechts, y0, h_innen, fill)

    def _pausen_segmente_mitlauf(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[tuple[dt.datetime, dt.datetime]]:
        pr = self._pausenprofil
        out: list[tuple[dt.datetime, dt.datetime]] = []
        d = t_top.date()
        limit = t_bot.date()
        while d <= limit:
            bloecke = pr.bloecke_fuer_wochentag(d.weekday())
            arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(d)
            if bloecke and arbeitszeit is not None:
                start_m, ende_m = arbeitszeit
                sh, sm = divmod(start_m, 60)
                eh, em = divmod(ende_m, 60)
                tws = self._datetime_standort(d, dt.time(sh, sm))
                twe = self._datetime_standort(d, dt.time(eh, em))
                for block in bloecke:
                    ta = self._datetime_standort(
                        d, dt.time(block.start_stunde, block.start_minute)
                    )
                    tb = self._datetime_standort(
                        d, dt.time(block.ende_stunde, block.ende_minute)
                    )
                    a = max(ta, tws, t_top)
                    b = min(tb, twe, t_bot)
                    if a < b:
                        out.append((a, b))
            d += dt.timedelta(days=1)
        return out

    def _zeichnen_pausen_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        fill = self._pausenprofil.pauseflaechen_farbe_hex()
        for ta, tb in self._pausen_segmente_mitlauf(t_top, t_bot):
            ya = self._dt_nach_y_mitlauf(ta, t_top, h_innen, y0)
            yb = self._dt_nach_y_mitlauf(tb, t_top, h_innen, y0)
            if yb < ya:
                ya, yb = yb, ya
            if yb - ya < 1.0:
                yb = ya + 1.0
            c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0)

    def zeichne_monats_tag_zelle_zeitbereiche(
        self,
        c: tk.Canvas,
        tag: dt.date,
        w: int,
        h: int,
        kf: KalenderFarbenPaket,
    ) -> None:
        """Monatsraster-Zelle: Wach/Schlaf, Regelarbeit, Pausen, Wege (0–24 h wie Streifen)."""
        alt_cache = self._sichtbar_cache
        try:
            self._monats_blatt_datum_override = tag
            self._sichtbar_cache = None
            y0 = float(self.RAND_OBEN)
            y1 = float(h) - float(self.RAND_UNTEN)
            h_innen = max(y1 - y0, 1.0)
            xk = 0.0
            x_rechts = float(w)
            pf = self._phasen_farben_aktuell()
            c.create_rectangle(xk, y0, x_rechts, y1, fill=kf.HINTERGRUND_BLATT, width=0)
            for m0, m1, ist_wach in self._phasen_segmente_sichtbar():
                fill = pf.wach_hex if ist_wach else pf.schlaf_hex
                ya = self._minute_nach_y(m0, h_innen, y0)
                yb = self._minute_nach_y(m1, h_innen, y0)
                if yb < ya:
                    ya, yb = yb, ya
                if yb - ya < 1.0:
                    yb = ya + 1.0
                c.create_rectangle(xk, ya, x_rechts, yb, fill=fill, width=0)
            self._zeichnen_regelarbeit_statisch(c, xk, x_rechts, y0, h_innen)
            self._zeichnen_pausen_statisch(c, xk, x_rechts, y0, h_innen)
            self._zeichnen_wegezeit_statisch(c, xk, x_rechts, y0, h_innen)
            for m0, m1 in segmente_minuten_fuer_tag(tag, ZoneInfo(self._standort.zeitzone)):
                self._rechteck_minuten_statisch(
                    c,
                    m0,
                    m1,
                    xk,
                    x_rechts,
                    y0,
                    h_innen,
                    kf.ZEITAUFZEICHNUNG_FLACHE,
                )
            self._zeichnen_krankstatus_statisch(c, tag, xk, x_rechts, y0, y1)
        finally:
            self._monats_blatt_datum_override = None
            self._sichtbar_cache = alt_cache

    def _rechteck_minuten_statisch(
        self,
        c: tk.Canvas,
        minute_lo: float,
        minute_hi: float,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
        fill: str,
        *,
        tags: tuple[str, ...] = (),
    ) -> None:
        vis_lo, vis_hi = self._sichtbarer_minutenbereich()
        lo = max(vis_lo, minute_lo)
        hi = min(vis_hi, minute_hi)
        if lo >= hi:
            return
        ya = self._minute_nach_y(lo, h_innen, y0)
        yb = self._minute_nach_y(hi, h_innen, y0)
        if yb < ya:
            ya, yb = yb, ya
        if yb - ya < 1.0:
            yb = ya + 1.0
        c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0, tags=tags)

    def _zeichnen_wegezeit_statisch(
        self,
        c: tk.Canvas,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        w = self._wegezeit
        if w.minuten_hin_zur_arbeit <= 0 and w.minuten_rueck_nach_hause <= 0:
            return
        arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(
            self._effektives_datum_fuer_zeichnung()
        )
        if arbeitszeit is None:
            return
        fill = w.wegflaechen_farbe_hex()
        tag_ende = 24.0 * 60.0

        if w.minuten_hin_zur_arbeit > 0:
            a_start = float(arbeitszeit[0])
            hin_lo = max(0.0, a_start - float(w.minuten_hin_zur_arbeit))
            hin_hi = a_start
            self._rechteck_minuten_statisch(c, hin_lo, hin_hi, x_links, x_rechts, y0, h_innen, fill)

        if w.minuten_rueck_nach_hause > 0:
            a_ende = float(arbeitszeit[1])
            rueck_lo = a_ende
            rueck_hi = min(tag_ende, rueck_lo + float(w.minuten_rueck_nach_hause))
            self._rechteck_minuten_statisch(c, rueck_lo, rueck_hi, x_links, x_rechts, y0, h_innen, fill)

    def _wege_segmente_mitlauf(
        self, t_top: dt.datetime, t_bot: dt.datetime
    ) -> list[tuple[dt.datetime, dt.datetime]]:
        w = self._wegezeit
        if w.minuten_hin_zur_arbeit <= 0 and w.minuten_rueck_nach_hause <= 0:
            return []
        out: list[tuple[dt.datetime, dt.datetime]] = []
        d = t_top.date()
        limit = t_bot.date()
        while d <= limit:
            arbeitszeit = self._arbeitszeit_fuer_tag_ohne_krankmeldung(d)
            if arbeitszeit is not None:
                start_m, ende_m = arbeitszeit
                sh, sm = divmod(start_m, 60)
                eh, em = divmod(ende_m, 60)
                t_start = self._datetime_standort(d, dt.time(sh, sm))
                t_ende = self._datetime_standort(d, dt.time(eh, em))
                if w.minuten_hin_zur_arbeit > 0:
                    ta = t_start - dt.timedelta(minutes=w.minuten_hin_zur_arbeit)
                    tb = t_start
                    a = max(ta, t_top)
                    b = min(tb, t_bot)
                    if a < b:
                        out.append((a, b))
                if w.minuten_rueck_nach_hause > 0:
                    ta = t_ende
                    tb = t_ende + dt.timedelta(minutes=w.minuten_rueck_nach_hause)
                    a = max(ta, t_top)
                    b = min(tb, t_bot)
                    if a < b:
                        out.append((a, b))
            d += dt.timedelta(days=1)
        return out

    def _zeichnen_wegezeit_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        fill = self._wegezeit.wegflaechen_farbe_hex()
        for ta, tb in self._wege_segmente_mitlauf(t_top, t_bot):
            ya = self._dt_nach_y_mitlauf(ta, t_top, h_innen, y0)
            yb = self._dt_nach_y_mitlauf(tb, t_top, h_innen, y0)
            if yb < ya:
                ya, yb = yb, ya
            if yb - ya < 1.0:
                yb = ya + 1.0
            c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0)

    def _zeichnen_zeitaufzeichnung_statisch(
        self,
        c: tk.Canvas,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        kf = kalender_farben()
        fill = kf.ZEITAUFZEICHNUNG_FLACHE
        tag = self._effektives_datum_fuer_zeichnung()
        for m0, m1, titel, kid in segmente_minuten_mit_titel_fuer_tag(tag, self._standort_tz):
            rtags: tuple[str, ...] = ("zeitaufzeichnung",)
            if kid:
                rtags = ("zeitaufzeichnung", f"kid:{kid}")
            self._rechteck_minuten_statisch(
                c, m0, m1, x_links, x_rechts, y0, h_innen, fill, tags=rtags
            )
            symbol = self._zeitaufzeichnung_symbol_aus_titel(titel)
            if symbol:
                y_mitte = (self._minute_nach_y(m0, h_innen, y0) + self._minute_nach_y(m1, h_innen, y0)) / 2.0
                c.create_text(
                    x_links + 6,
                    y_mitte,
                    anchor=tk.W,
                    text=symbol,
                    fill=kf.TEXT_ZEIT,
                    font=("Segoe UI", 9),
                )

    def _zeichnen_zeitaufzeichnung_mitlauf(
        self,
        c: tk.Canvas,
        t_top: dt.datetime,
        t_bot: dt.datetime,
        x_links: float,
        x_rechts: float,
        y0: float,
        h_innen: float,
    ) -> None:
        kf = kalender_farben()
        fill = kf.ZEITAUFZEICHNUNG_FLACHE
        tz = ZoneInfo(self._standort.zeitzone)
        for ta, tb, titel, kid in segmente_datetime_mitlauf_mit_titel(t_top, t_bot, tz):
            ya = self._dt_nach_y_mitlauf(ta, t_top, h_innen, y0)
            yb = self._dt_nach_y_mitlauf(tb, t_top, h_innen, y0)
            if yb < ya:
                ya, yb = yb, ya
            if yb - ya < 1.0:
                yb = ya + 1.0
            mtags: tuple[str, ...] = ("zeitaufzeichnung",)
            if kid:
                mtags = ("zeitaufzeichnung", f"kid:{kid}")
            c.create_rectangle(x_links, ya, x_rechts, yb, fill=fill, width=0, tags=mtags)
            symbol = self._zeitaufzeichnung_symbol_aus_titel(titel)
            if symbol:
                c.create_text(
                    x_links + 6,
                    (ya + yb) / 2.0,
                    anchor=tk.W,
                    text=symbol,
                    fill=kf.TEXT_ZEIT,
                    font=("Segoe UI", 9),
                )

    @staticmethod
    def _zeitaufzeichnung_symbol_aus_titel(titel: str) -> str:
        """Liest ein optionales Prefix-Symbol aus dem Titel (z. B. '▤ Schatzkiste ...')."""
        if not titel:
            return ""
        erstes = titel.strip()[:1]
        if not erstes:
            return ""
        if erstes.isalnum():
            return ""
        return erstes

    def _bei_klick(self, event: tk.Event) -> None:
        hit = self._krank_tag_und_text_unter_koordinate(float(event.x), float(event.y))
        if hit is not None:
            tag, _ = hit
            eintrag = eintrag_fuer_tag(tag)
            if eintrag is not None:
                top = self.winfo_toplevel()
                setattr(top, "_ahds_krankmeldung_id", eintrag.id)
                try:
                    top.event_generate("<<KrankmeldungOeffnen>>", when="tail")
                except tk.TclError:
                    pass
                return
        try:
            c = self._canvas
            for item in c.find_overlapping(float(event.x), float(event.y), float(event.x), float(event.y)):
                for tg in c.gettags(item):
                    if tg.startswith("kid:"):
                        kid = tg[4:].strip()
                        if kid:
                            top = self.winfo_toplevel()
                            setattr(top, "_ahds_kontakt_id", kid)
                            try:
                                top.event_generate("<<KontaktOeffnen>>", when="tail")
                            except tk.TclError:
                                pass
                            return
        except tk.TclError:
            pass
        gruppe = self._zoom_sync_gruppe
        if gruppe is not None and len(gruppe) in (3, 7):
            naechste = gruppe[len(gruppe) // 2]._naechste_zoom_stufe()
            for p in gruppe:
                p._zoom = naechste
                p._zeichnen()
            return
        naechste = self._naechste_zoom_stufe()
        self._zoom = naechste
        self._zeichnen()

    def _bei_groessenwechsel(self, _event: tk.Event) -> None:
        if not self._kalenderblatt_zeigen:
            try:
                pw = self.winfo_width()
                xk = self._x_kalender_start()
                if pw > 1:
                    self._canvas.configure(width=min(pw, xk) if xk > 0 else pw)
            except tk.TclError:
                pass
        self._zeichnen()

    def _plant_naechstes_update(self) -> None:
        if not self._periodisches_neuzeichnen:
            return
        if self._nach_update_id is not None:
            self.after_cancel(self._nach_update_id)
        self._nach_update_id = self.after(1000, self._tick)

    def _tick(self) -> None:
        self._zeichnen()
        self._plant_naechstes_update()

    def _zeichnen(self) -> None:
        if self._zoom is ZoomStufe.MITLAUF and self._mitlauf_moeglich():
            self._zeichnen_mitlauf()
        else:
            self._zeichnen_statischer_tag()

    def _zeichnen_statischer_tag(self) -> None:
        self._sichtbar_cache = self._sichtbarer_minutenbereich_berechnen()
        try:
            self._zeichnen_statischer_tag_gezeichnet()
        finally:
            self._sichtbar_cache = None

    def _zeichnen_statischer_tag_gezeichnet(self) -> None:
        c = self._canvas
        c.delete("all")
        w = max(c.winfo_width(), 2)
        h = max(c.winfo_height(), 2)
        if not self._kalenderblatt_zeigen:
            try:
                pw = self.winfo_width()
                if pw > 1:
                    w = min(w, pw)
            except tk.TclError:
                pass
        volle_zl = self._mit_zeitleiste_und_sonne
        x_text = self.ZEITLEISTE_TEXT_BREITE if volle_zl else 0
        xk = self._x_kalender_start()
        if not self._kalenderblatt_zeigen and xk > 0:
            w = max(2, min(w, xk))
        x0 = xk
        y0 = self.RAND_OBEN
        y1 = h - self._rand_unten
        h_innen = max(y1 - y0, 1.0)
        x_rechts = w - self._rand_rechts
        kf = kalender_farben()
        pf = self._phasen_farben_aktuell()
        blatt = self._kalenderblatt_zeigen

        if volle_zl:
            c.create_rectangle(0, 0, x_text, h, fill=kf.HINTERGRUND_ZEITLEISTE, width=0)
            if self._mit_sonnenspalte:
                c.create_rectangle(x_text, 0, xk, h, fill="#000000", width=0)
                self._zeichnen_sonnenspalte_statisch(c, x_text, xk, y0, y1, h_innen)
                c.create_line(x_text, 0, x_text, h, fill=kf.TRENNLINIE, width=1)
        if blatt:
            c.create_rectangle(xk, 0, w, h, fill=kf.HINTERGRUND_BLATT, width=0)
        elif w > xk:
            c.create_rectangle(xk, 0, w, h, fill=kf.HINTERGRUND_ZEITLEISTE, width=0)

        if blatt:
            for m0, m1, ist_wach in self._phasen_segmente_sichtbar():
                fill = pf.wach_hex if ist_wach else pf.schlaf_hex
                ya = self._minute_nach_y(m0, h_innen, y0)
                yb = self._minute_nach_y(m1, h_innen, y0)
                if yb < ya:
                    ya, yb = yb, ya
                if yb - ya < 1.0:
                    yb = ya + 1.0
                c.create_rectangle(xk, ya, x_rechts, yb, fill=fill, width=0)

            self._zeichnen_krankstatus_statisch(
                c,
                self._effektives_datum_fuer_zeichnung(),
                xk,
                x_rechts,
                y0,
                y1,
            )
            self._zeichnen_regelarbeit_statisch(c, xk, x_rechts, y0, h_innen)
            self._zeichnen_pausen_statisch(c, xk, x_rechts, y0, h_innen)
            self._zeichnen_wegezeit_statisch(c, xk, x_rechts, y0, h_innen)
            self._zeichnen_zeitaufzeichnung_statisch(c, xk, x_rechts, y0, h_innen)

            c.create_rectangle(x_rechts, 0, w, h, fill=kf.HINTERGRUND_BLATT, width=0)
        if xk > 0:
            c.create_line(xk, 0, xk, h, fill=kf.TRENNLINIE, width=1)

        start_m, ende_m = self._sichtbarer_minutenbereich()
        erste_stunde = int(math.ceil(start_m / 60.0))
        letzte_stunde = int(math.floor(ende_m / 60.0))
        step = self._stunden_raster_intervall
        st = erste_stunde
        if step > 1:
            r = st % step
            if r != 0:
                st += step - r
        x_lin_lo = 0.0 if not blatt else float(x0)
        x_lin_hi = float(xk) if not blatt else float(x_rechts)
        zu_x0 = 0 if not blatt else x0
        zu_xr = xk if not blatt else x_rechts
        for stunde in range(st, letzte_stunde + 1, step):
            minute = stunde * 60
            if minute < start_m or minute > ende_m:
                continue
            y = self._minute_nach_y(minute, h_innen, y0)
            if blatt:
                c.create_line(x_lin_lo, y, x_lin_hi, y, fill=kf.RASTER_STUNDE, width=1)
            if volle_zl and stunde < 24 and (blatt or stunde != 0):
                label = f"{stunde:02d}:00"
                c.create_text(
                    6,
                    y,
                    anchor=tk.W,
                    text=label,
                    fill=kf.TEXT_ZEIT,
                    font=("Segoe UI", 9),
                )

        if volle_zl:
            self._zeichnen_nautische_zeiten_statisch(
                c, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_sonnenauf_untergang_statisch(
                c, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_kulmination_zeiten_statisch(
                c, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_zeitumstellung_statisch(
                c, zu_x0, zu_xr, x_text, y0, y1, h_innen, kf
            )
        else:
            self._zeichnen_zeitumstellung_statisch(
                c, zu_x0, zu_xr, x_text, y0, y1, h_innen, kf
            )

        if blatt:
            self._zeichnen_vertikale_dreier_tagestrennung(
                c, float(xk), float(x_rechts), y1
            )
        wt_xk = 0.0 if not blatt else float(xk)
        wt_rx = float(xk) if not blatt else float(x_rechts)
        self._zeichnen_wochen_tag_trennung(
            c, float(w), float(h), wt_xk, wt_rx, y0, y1, kf
        )

        if blatt and self._datum == self._heute_im_standort():
            jetzt = dt.datetime.now(self._standort_tz)
            minuten_jetzt = self._minuten_seit_anzeige_mitternacht(jetzt)
            if start_m <= minuten_jetzt <= ende_m:
                y_j = self._minute_nach_y(minuten_jetzt, h_innen, y0)
                kompakt = (
                    self._kalender_raster_modus
                    in (
                        KalenderRasterModus.WOCHE_HORIZONTAL,
                        KalenderRasterModus.ARBEITSWOCHE_HORIZONTAL,
                    )
                )
                self._zeichnen_jetzt_zeiger(
                    c,
                    kf,
                    x0,
                    x_rechts,
                    jetzt,
                    y_mitte=y_j,
                    kompakt_banner=kompakt,
                )
                self._jetzt_zeiger_nach_oben(c)

    def _zeichnen_mitlauf(self) -> None:
        c = self._canvas
        c.delete("all")
        w = max(c.winfo_width(), 2)
        h = max(c.winfo_height(), 2)
        volle_zl = self._mit_zeitleiste_und_sonne
        x_text = self.ZEITLEISTE_TEXT_BREITE if volle_zl else 0
        xk = self._x_kalender_start()
        x0 = xk
        y0 = self.RAND_OBEN
        y1 = h - self._rand_unten
        h_innen = max(y1 - y0, 1.0)
        x_rechts = w - self._rand_rechts
        blatt = self._kalenderblatt_zeigen

        tz = ZoneInfo(self._standort.zeitzone)
        t_top = dt.datetime.now(tz).replace(microsecond=0)
        t_bot = t_top + dt.timedelta(hours=self.MITLAUF_SPANNE_STUNDEN)
        kf = kalender_farben()
        pf = self._phasen_farben_aktuell()

        if volle_zl:
            c.create_rectangle(0, 0, x_text, h, fill=kf.HINTERGRUND_ZEITLEISTE, width=0)
            if self._mit_sonnenspalte:
                c.create_rectangle(x_text, 0, xk, h, fill="#000000", width=0)
                self._zeichnen_sonnenspalte_mitlauf(c, t_top, x_text, xk, y0, h_innen)
                c.create_line(x_text, 0, x_text, h, fill=kf.TRENNLINIE, width=1)
        if blatt:
            c.create_rectangle(xk, 0, w, h, fill=kf.HINTERGRUND_BLATT, width=0)
        elif w > xk:
            c.create_rectangle(xk, 0, w, h, fill=kf.HINTERGRUND_ZEITLEISTE, width=0)

        if blatt:
            for ta, tb, ist_wach in self._phasen_segmente_mitlauf(t_top, t_bot):
                fill = pf.wach_hex if ist_wach else pf.schlaf_hex
                ya = self._dt_nach_y_mitlauf(ta, t_top, h_innen, y0)
                yb = self._dt_nach_y_mitlauf(tb, t_top, h_innen, y0)
                if yb < ya:
                    ya, yb = yb, ya
                if yb - ya < 1.0:
                    yb = ya + 1.0
                c.create_rectangle(xk, ya, x_rechts, yb, fill=fill, width=0)

            self._zeichnen_krankstatus_mitlauf(
                c, t_top, t_bot, xk, x_rechts, y0, h_innen
            )
            self._zeichnen_regelarbeit_mitlauf(c, t_top, t_bot, xk, x_rechts, y0, h_innen)
            self._zeichnen_pausen_mitlauf(c, t_top, t_bot, xk, x_rechts, y0, h_innen)
            self._zeichnen_wegezeit_mitlauf(c, t_top, t_bot, xk, x_rechts, y0, h_innen)
            self._zeichnen_zeitaufzeichnung_mitlauf(
                c, t_top, t_bot, xk, x_rechts, y0, h_innen
            )

            c.create_rectangle(x_rechts, 0, w, h, fill=kf.HINTERGRUND_BLATT, width=0)
        if xk > 0:
            c.create_line(xk, 0, xk, h, fill=kf.TRENNLINIE, width=1)

        x_lin_lo = 0.0 if not blatt else float(x0)
        x_lin_hi = float(xk) if not blatt else float(x_rechts)
        zu_x0 = 0 if not blatt else x0
        zu_xr = xk if not blatt else x_rechts

        stunden_marken = self._stunden_marken_mitlauf(t_top, t_bot)
        for tm in stunden_marken:
            y = self._dt_nach_y_mitlauf(tm, t_top, h_innen, y0)
            if y < y0 or y > y1:
                continue
            c.create_line(x_lin_lo, y, x_lin_hi, y, fill=kf.RASTER_STUNDE, width=1)

        if blatt:
            self._zeichnen_mitlauf_tageswechsel(
                c, t_top, t_bot, xk, x_rechts, y0, y1, h_innen, kf
            )

        if volle_zl:
            for tm in stunden_marken:
                y = self._dt_nach_y_mitlauf(tm, t_top, h_innen, y0)
                if y < y0 or y > y1:
                    continue
                label = self._format_zeit_mitlauf(tm)
                c.create_text(
                    6,
                    y,
                    anchor=tk.W,
                    text=label,
                    fill=kf.TEXT_ZEIT,
                    font=("Segoe UI", 9),
                )

            self._zeichnen_nautische_zeiten_mitlauf(
                c, t_top, t_bot, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_sonnenauf_untergang_mitlauf(
                c, t_top, t_bot, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_kulmination_zeiten_mitlauf(
                c, t_top, t_bot, x_text, y0, y1, h_innen, kf
            )
            self._zeichnen_zeitumstellung_mitlauf(
                c, t_top, t_bot, zu_x0, zu_xr, x_text, y0, y1, h_innen, kf
            )
        else:
            self._zeichnen_zeitumstellung_mitlauf(
                c, t_top, t_bot, zu_x0, zu_xr, x_text, y0, y1, h_innen, kf
            )

        wt_xk = 0.0 if not blatt else float(xk)
        wt_rx = float(xk) if not blatt else float(x_rechts)
        self._zeichnen_wochen_tag_trennung(
            c, float(w), float(h), wt_xk, wt_rx, y0, y1, kf
        )

        if blatt:
            self._zeichnen_jetzt_zeiger(
                c, kf, x0, x_rechts, t_top, y_oben=y0
            )
            self._jetzt_zeiger_nach_oben(c)
