"""Monatsraster: Wochentagsspalten, eine Zeile pro Kalenderwoche."""

from __future__ import annotations

import calendar
import datetime as dt
from collections.abc import Callable
from enum import Enum, auto
import tkinter as tk
from typing import Any

from locales import get_string

from modules.krankmeldung.speicher import (
    eintrag_fuer_tag,
    ist_krankgeschrieben_am,
    ist_wiedervorstellung_am,
)
from modules.theming.farben import kalender_farben

from .farb_hilfen import MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR, hex_rgb_mit_faktor
from .tagesansicht import Tagesansicht

_StreifenBauer = Callable[[tk.Misc, dt.date], "Tagesansicht"]


def _mittwoch_referenztag(
    raster_start: dt.date, zeile: int, wochenstart: KalenderMonatWochenstart
) -> dt.date:
    """Mittwoch der Kalenderwoche in Zeile ``zeile`` (0-basiert), passend zur Spaltenreihenfolge."""
    woche_anfang = raster_start + dt.timedelta(days=zeile * 7)
    if wochenstart is KalenderMonatWochenstart.MONTAG:
        return woche_anfang + dt.timedelta(days=2)
    return woche_anfang + dt.timedelta(days=3)


class KalenderMonatWochenstart(Enum):
    """Erste Spalte des Rasters."""

    MONTAG = auto()
    SONNTAG = auto()


class KalenderMonatRanddarstellung(Enum):
    """Nachbarmonate in den ersten/letzten Wochen."""

    #: Nur Tage des gewählten Monats; Randzellen leer.
    NUR_AKTUELLER_MONAT = auto()
    #: Vormonat/Nächstmonat in den Randwochen sichtbar.
    MIT_RANDMONAT_TAGEN = auto()


def _erster_raster_tag(y: int, m: int, wochenstart: KalenderMonatWochenstart) -> dt.date:
    first = dt.date(y, m, 1)
    if wochenstart is KalenderMonatWochenstart.MONTAG:
        back = first.weekday()
    else:
        back = (first.weekday() + 1) % 7
    return first - dt.timedelta(days=back)


def _raster_zeilen(start: dt.date, y: int, m: int) -> int:
    last = dt.date(y, m, calendar.monthrange(y, m)[1])
    return (last - start).days // 7 + 1


def _wochentag_spalten_indices(
    wochenstart: KalenderMonatWochenstart,
) -> tuple[int, ...]:
    if wochenstart is KalenderMonatWochenstart.MONTAG:
        return (0, 1, 2, 3, 4, 5, 6)
    return (6, 0, 1, 2, 3, 4, 5)


def _montag_der_iso_woche_mit_tag(d: dt.date) -> dt.date:
    """Montag der ISO-8601-Kalenderwoche, die den Tag ``d`` enthält."""
    return d - dt.timedelta(days=d.weekday())


def _iso_kw_nummer(montag: dt.date) -> int:
    return int(montag.isocalendar()[1])


def _monat_hover_randfarbe(kf: Any) -> str:
    """Dünner Rahmen bei Mausover (auch statt des roten Heute-Rands)."""
    return kf.TEXT_ZEIT


class MonatsRasterAnsicht(tk.Frame):
    """Kalendermonat als Gitter (Kopfzeile + eine Zeile je Kalenderwoche)."""

    def __init__(
        self,
        master: tk.Misc,
        mitte: dt.date,
        wochenstart: KalenderMonatWochenstart,
        rand: KalenderMonatRanddarstellung,
        *,
        locale: str = "de",
        on_tag: Callable[[dt.date], None] | None = None,
        on_tag_einzelansicht: Callable[[dt.date], None] | None = None,
        on_kw_zeile: Callable[[dt.date], None] | None = None,
        streifen_bau: _StreifenBauer | None = None,
        streifen_breite_px: int = 0,
        transpose: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._locale = locale
        self._on_tag = on_tag
        self._on_tag_einzelansicht = on_tag_einzelansicht
        self._on_kw_zeile = on_kw_zeile
        self._wochenstart = wochenstart
        self._rand = rand
        self._transpose = transpose
        self._jahr = mitte.year
        self._monat = mitte.month
        self._streifen_bau = streifen_bau
        self._streifen_breite_px = max(0, int(streifen_breite_px))
        self._streifen_refs: list[Any] = []
        self._zellen_refs: list[
            tuple[tk.Frame, tk.Label | tk.Canvas | None, dt.date]
        ] = []
        self._canvas_heute: tk.Canvas | None = None
        #: Zelle, über der die Maus schwebt (Rahmen; Jetzt-Zeiger auf Canvas unverändert).
        self._monat_zelle_hover_fr: tk.Frame | None = None
        self._krank_tooltip: tk.Toplevel | None = None
        self._monat_jetzt_id: str | None = None
        self._kw_labels: list[tk.Label] = []
        self._raster = tk.Frame(self, bd=0, highlightthickness=0)
        self._raster.pack(fill=tk.BOTH, expand=True)
        self._aufbauen_raster()

    def destroy(self) -> None:
        if self._monat_jetzt_id is not None:
            try:
                self.after_cancel(self._monat_jetzt_id)
            except tk.TclError:
                pass
            self._monat_jetzt_id = None
        super().destroy()

    def _heute_datum(self) -> dt.date:
        if self._streifen_refs:
            return self._streifen_refs[0]._heute_im_standort()
        return dt.date.today()

    def _plant_monat_jetzt_tick(self) -> None:
        if self._monat_jetzt_id is not None:
            try:
                self.after_cancel(self._monat_jetzt_id)
            except tk.TclError:
                pass
            self._monat_jetzt_id = None
        if self._canvas_heute is None or not self._streifen_refs:
            return
        self._monat_jetzt_id = self.after(1000, self._monat_jetzt_tick)

    def _monat_jetzt_tick(self) -> None:
        self._monat_jetzt_id = None
        if self._canvas_heute is None or not self.winfo_ismapped():
            return
        try:
            self._monats_wochentag_zelle_zeichnen(
                self._canvas_heute, self._heute_datum()
            )
        except tk.TclError:
            return
        self._plant_monat_jetzt_tick()

    @property
    def jahr_monat(self) -> tuple[int, int]:
        return (self._jahr, self._monat)

    @property
    def streifen_ansichten(self) -> tuple[Any, ...]:
        return tuple(self._streifen_refs)

    def monat_setzen(self, mitte: dt.date) -> None:
        self._jahr = mitte.year
        self._monat = mitte.month
        self._aufbauen_raster()

    def wochenstart_setzen(self, ws: KalenderMonatWochenstart) -> None:
        if ws is self._wochenstart:
            return
        self._wochenstart = ws
        self._aufbauen_raster()

    def randdarstellung_setzen(self, r: KalenderMonatRanddarstellung) -> None:
        if r is self._rand:
            return
        self._rand = r
        self._aufbauen_raster()

    def transpose_setzen(self, transponiert: bool) -> None:
        if transponiert is self._transpose:
            return
        self._transpose = transponiert
        self._aufbauen_raster()

    def darstellung_auffrischen(self) -> None:
        self._zellen_malen()
        self._kw_spalte_farben()
        for tv in self._streifen_refs:
            tv.darstellung_auffrischen()

    def _kw_spalte_farben(self) -> None:
        kf = kalender_farben()
        for lb in self._kw_labels:
            lb.configure(bg=kf.HINTERGRUND_ZEITLEISTE, fg=kf.TEXT_ZEIT)

    def layout_nach_elterngroesse(self) -> None:
        """Nach Moduswechsel oder Größenänderung: Tk-Geometrie nachziehen (Zeilen bis unten)."""
        self.update_idletasks()
        self._raster.update_idletasks()
        for tv in self._streifen_refs:
            try:
                tv.update_idletasks()
            except tk.TclError:
                pass
        try:
            self.pack_configure(fill=tk.BOTH, expand=True)
        except tk.TclError:
            pass

    def _aufbauen_raster_transponiert(self) -> None:
        """Wochen als Spalten, Wochentage als Zeilen (wie Mini-Monat transponiert)."""
        if self._monat_jetzt_id is not None:
            try:
                self.after_cancel(self._monat_jetzt_id)
            except tk.TclError:
                pass
            self._monat_jetzt_id = None
        self._canvas_heute = None
        self._monat_zelle_hover_fr = None
        for w in self._raster.winfo_children():
            w.destroy()
        self._zellen_refs.clear()
        self._streifen_refs.clear()
        self._kw_labels.clear()
        for r in range(1, 12):
            self._raster.grid_rowconfigure(r, weight=0, minsize=0, uniform="")
        y, m = self._jahr, self._monat
        start = _erster_raster_tag(y, m, self._wochenstart)
        n_zeilen = _raster_zeilen(start, y, m)
        kf = kalender_farben()
        idx = _wochentag_spalten_indices(self._wochenstart)
        linie = 1
        self._raster.configure(bg=kf.RASTER_STUNDE)
        mit_streifen = self._streifen_bau is not None and self._streifen_breite_px > 0

        if mit_streifen:
            hid = tk.Frame(self._raster, width=1, height=1, bd=0, highlightthickness=0)
            hid.place(x=-3000, y=-3000)
            ref0 = _mittwoch_referenztag(start, 0, self._wochenstart)
            assert self._streifen_bau is not None
            tv0 = self._streifen_bau(hid, ref0)
            self._streifen_refs.append(tv0)

        for c in range(1, 12):
            self._raster.grid_columnconfigure(c, weight=0, minsize=0, uniform="")
        self._raster.grid_columnconfigure(0, weight=0, minsize=44)
        for wi in range(n_zeilen):
            self._raster.grid_columnconfigure(
                wi + 1, weight=1, uniform="monat_spalte_tr"
            )
        self._raster.grid_rowconfigure(0, weight=0)
        for r in range(1, 8):
            self._raster.grid_rowconfigure(r, weight=1, uniform="monat_zeile_tr")

        ecke = tk.Label(
            self._raster,
            text="",
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            bd=0,
            highlightthickness=0,
        )
        ecke.grid(row=0, column=0, sticky="nsew", padx=(linie, linie), pady=(linie, linie))
        self._kw_labels.append(ecke)

        for z in range(n_zeilen):
            zeilen_anfang = start + dt.timedelta(days=z * 7)
            kw_nr = _iso_kw_nummer(_montag_der_iso_woche_mit_tag(zeilen_anfang))
            h_kw = tk.Label(
                self._raster,
                text=f"{kw_nr:02d}",
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 9, "bold"),
                bd=0,
                highlightthickness=0,
            )
            h_kw.grid(
                row=0,
                column=z + 1,
                sticky="nsew",
                padx=(0, linie),
                pady=(linie, linie),
            )
            self._kw_labels.append(h_kw)
            ref_woche = _mittwoch_referenztag(start, z, self._wochenstart)
            self._kw_nummer_binden(h_kw, ref_woche)

        for c in range(7):
            wd = idx[c]
            lb_wt = tk.Label(
                self._raster,
                text=get_string(f"kalender.wochentag_lang.{wd}", self._locale),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 9, "bold"),
                bd=0,
                highlightthickness=0,
                padx=2,
                pady=4,
            )
            lb_wt.grid(
                row=c + 1,
                column=0,
                sticky="nsew",
                padx=(linie, linie),
                pady=(0, linie),
            )
            self._kw_labels.append(lb_wt)

        heute: dt.date | None = None
        for z in range(n_zeilen):
            if heute is None:
                heute = self._heute_datum()
            for c in range(7):
                tag = start + dt.timedelta(days=z * 7 + c)
                fr = tk.Frame(
                    self._raster,
                    bd=0,
                    highlightthickness=0,
                    bg=kf.HINTERGRUND_BLATT,
                )
                fr.grid(
                    row=c + 1,
                    column=z + 1,
                    sticky="nsew",
                    padx=(0, linie),
                    pady=(0, linie),
                )
                im_monat = tag.month == m and tag.year == y
                if self._rand is KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT and (
                    not im_monat
                ):
                    fr.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
                    self._zellen_refs.append((fr, None, tag))
                elif mit_streifen:
                    cv = tk.Canvas(
                        fr,
                        highlightthickness=0,
                        bd=0,
                        bg=kf.HINTERGRUND_BLATT,
                        cursor="hand2"
                        if im_monat
                        or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                        else "arrow",
                    )
                    cv.pack(fill=tk.BOTH, expand=True)
                    cv.bind(
                        "<Configure>",
                        lambda e, canvas=cv, datum=tag: self._monats_wochentag_zelle_zeichnen(
                            canvas, datum
                        ),
                    )
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._monat_tagzelle_klick_und_hover(fr, cv, tag)
                    if tag == heute:
                        fr.configure(
                            highlightthickness=2,
                            highlightbackground=kf.JETZT_ZEIGER,
                        )
                        self._canvas_heute = cv
                    self._zellen_refs.append((fr, cv, tag))
                else:
                    tl = tk.Label(
                        fr,
                        text=str(tag.day),
                        bg=kf.HINTERGRUND_BLATT,
                        fg=kf.TEXT_ZEIT,
                        font=("Segoe UI", 11),
                        bd=0,
                        highlightthickness=0,
                        cursor="hand2"
                        if im_monat
                        or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                        else "arrow",
                    )
                    tl.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
                    if not im_monat:
                        tl.configure(fg=kf.RASTER_STUNDE)
                    if tag == heute:
                        fr.configure(
                            highlightthickness=2,
                            highlightbackground=kf.JETZT_ZEIGER,
                        )
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._monat_tagzelle_klick_und_hover(fr, tl, tag)
                    self._zellen_refs.append((fr, tl, tag))

        self._zellen_malen()
        self._plant_monat_jetzt_tick()
        self.after_idle(self._layout_nach_raster_aufbau)

    def _aufbauen_raster(self) -> None:
        if self._transpose:
            self._aufbauen_raster_transponiert()
            return
        if self._monat_jetzt_id is not None:
            try:
                self.after_cancel(self._monat_jetzt_id)
            except tk.TclError:
                pass
            self._monat_jetzt_id = None
        self._canvas_heute = None
        self._monat_zelle_hover_fr = None
        for w in self._raster.winfo_children():
            w.destroy()
        self._zellen_refs.clear()
        self._streifen_refs.clear()
        self._kw_labels.clear()
        #: Monate haben 4–6 Wochenzeilen; alte ``grid_rowconfigure`` (uniform/weight)
        #: bleibt sonst für höhere Zeilenindizes bestehen → leere Zeile mit weight teilt
        #: die Höhe mit und staucht die sichtbaren Wochen (oft nach „Letzter Monat“).
        for r in range(1, 12):
            self._raster.grid_rowconfigure(r, weight=0, minsize=0, uniform="")
        y, m = self._jahr, self._monat
        start = _erster_raster_tag(y, m, self._wochenstart)
        n_zeilen = _raster_zeilen(start, y, m)
        kf = kalender_farben()
        idx = _wochentag_spalten_indices(self._wochenstart)
        #: 1 px Fuge in Rasterfarbe = dünne Linie wie horizontales Stundenraster.
        linie = 1
        self._raster.configure(bg=kf.RASTER_STUNDE)
        mit_streifen = self._streifen_bau is not None and self._streifen_breite_px > 0
        col_kw = 1 if mit_streifen else 0
        col_tag_start = col_kw + 1

        if mit_streifen:
            self._raster.grid_columnconfigure(0, weight=0, minsize=self._streifen_breite_px)
        self._raster.grid_columnconfigure(col_kw, weight=0, minsize=44)
        for c in range(7):
            self._raster.grid_columnconfigure(
                col_tag_start + c,
                weight=1,
                uniform="monat_spalte",
            )
        self._raster.grid_rowconfigure(0, weight=0)
        for r in range(1, n_zeilen + 1):
            self._raster.grid_rowconfigure(
                r, weight=1, uniform="monat_zeile", minsize=0
            )

        if mit_streifen:
            #: Feste Breite + propagate aus: sonst wächst die Spalte mit der Canvas der Tagesansicht.
            eck = tk.Frame(
                self._raster,
                width=self._streifen_breite_px,
                bd=0,
                highlightthickness=0,
                bg=kf.HINTERGRUND_ZEITLEISTE,
            )
            eck.grid(
                row=0,
                column=0,
                sticky="nsew",
                padx=(linie, linie),
                pady=(linie, linie),
            )
            eck.grid_propagate(False)

        kw_kopf = tk.Label(
            self._raster,
            text=get_string("kalender.raster_kw_spalte", self._locale),
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 9, "bold"),
            bd=0,
            highlightthickness=0,
            padx=2,
            pady=4,
        )
        kw_kopf.grid(
            row=0,
            column=col_kw,
            sticky="nsew",
            padx=(linie, linie),
            pady=(linie, linie),
        )
        self._kw_labels.append(kw_kopf)

        for c in range(7):
            wd = idx[c]
            lab = tk.Label(
                self._raster,
                text=get_string(f"kalender.wochentag_lang.{wd}", self._locale),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 9, "bold"),
                bd=0,
                highlightthickness=0,
                padx=2,
                pady=4,
            )
            lab.grid(
                row=0,
                column=col_tag_start + c,
                sticky="nsew",
                padx=(0, linie),
                pady=(linie, linie),
            )

        heute: dt.date | None = None
        for z in range(n_zeilen):
            if mit_streifen:
                ref = _mittwoch_referenztag(start, z, self._wochenstart)
                woche_fr = tk.Frame(self._raster, bd=0, highlightthickness=0)
                woche_fr.grid(
                    row=z + 1,
                    column=0,
                    sticky="nsew",
                    padx=(linie, 0),
                    pady=(0, linie),
                )
                assert self._streifen_bau is not None
                tv = self._streifen_bau(woche_fr, ref)
                self._streifen_refs.append(tv)
                tv.pack(fill=tk.BOTH, expand=True)
            if heute is None:
                heute = self._heute_datum()
            zeilen_anfang = start + dt.timedelta(days=z * 7)
            kw_nr = _iso_kw_nummer(_montag_der_iso_woche_mit_tag(zeilen_anfang))
            kw_zelle = tk.Label(
                self._raster,
                text=f"{kw_nr:02d}",
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 9, "bold"),
                bd=0,
                highlightthickness=0,
            )
            kw_zelle.grid(
                row=z + 1,
                column=col_kw,
                sticky="nsew",
                padx=(linie, linie),
                pady=(0, linie),
            )
            self._kw_labels.append(kw_zelle)
            ref_woche = _mittwoch_referenztag(start, z, self._wochenstart)
            self._kw_nummer_binden(kw_zelle, ref_woche)
            for c in range(7):
                tag = start + dt.timedelta(days=z * 7 + c)
                fr = tk.Frame(
                    self._raster,
                    bd=0,
                    highlightthickness=0,
                    bg=kf.HINTERGRUND_BLATT,
                )
                fr.grid(
                    row=z + 1,
                    column=col_tag_start + c,
                    sticky="nsew",
                    padx=(0, linie),
                    pady=(0, linie),
                )
                im_monat = tag.month == m and tag.year == y
                if self._rand is KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT and (
                    not im_monat
                ):
                    fr.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
                    self._zellen_refs.append((fr, None, tag))
                elif mit_streifen:
                    cv = tk.Canvas(
                        fr,
                        highlightthickness=0,
                        bd=0,
                        bg=kf.HINTERGRUND_BLATT,
                        cursor="hand2"
                        if im_monat
                        or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                        else "arrow",
                    )
                    cv.pack(fill=tk.BOTH, expand=True)
                    cv.bind(
                        "<Configure>",
                        lambda e, canvas=cv, datum=tag: self._monats_wochentag_zelle_zeichnen(
                            canvas, datum
                        ),
                    )
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._monat_tagzelle_klick_und_hover(fr, cv, tag)
                    if tag == heute:
                        fr.configure(
                            highlightthickness=2,
                            highlightbackground=kf.JETZT_ZEIGER,
                        )
                        self._canvas_heute = cv
                    self._zellen_refs.append((fr, cv, tag))
                else:
                    tl = tk.Label(
                        fr,
                        text=str(tag.day),
                        bg=kf.HINTERGRUND_BLATT,
                        fg=kf.TEXT_ZEIT,
                        font=("Segoe UI", 11),
                        bd=0,
                        highlightthickness=0,
                        cursor="hand2"
                        if im_monat
                        or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                        else "arrow",
                    )
                    tl.pack(expand=True, fill=tk.BOTH, padx=2, pady=2)
                    if not im_monat:
                        tl.configure(fg=kf.RASTER_STUNDE)
                    if tag == heute:
                        fr.configure(
                            highlightthickness=2,
                            highlightbackground=kf.JETZT_ZEIGER,
                        )
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._monat_tagzelle_klick_und_hover(fr, tl, tag)
                    self._zellen_refs.append((fr, tl, tag))

        self._zellen_malen()
        self._plant_monat_jetzt_tick()
        #: Wie beim ersten Einblenden der Monatsansicht: nach monat_setzen/wochenstart/…
        #: fehlt sonst oft die Tk-Nachberechnung → Zeilen gestaucht (Letzter Monat wirkte „ok“).
        self.after_idle(self._layout_nach_raster_aufbau)

    def _layout_nach_raster_aufbau(self) -> None:
        self.layout_nach_elterngroesse()
        self.after_idle(self._layout_nach_raster_aufbau_zweite)

    def _layout_nach_raster_aufbau_zweite(self) -> None:
        self.layout_nach_elterngroesse()
        #: Windows/Tk: manchmal erst nach kurzer Verzögerung stabile Elternhöhe.
        self.after(100, self.layout_nach_elterngroesse)

    def _klick_tag(self, d: dt.date) -> None:
        if self._on_tag_einzelansicht is not None:
            self._on_tag_einzelansicht(d)
            return
        if self._on_tag is not None:
            self._on_tag(d)

    def _krank_tooltip_text(self, tag: dt.date) -> str | None:
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

    def _krank_tooltip_anzeigen(self, text: str, x_root: int, y_root: int) -> None:
        if self._krank_tooltip is not None:
            try:
                self._krank_tooltip.destroy()
            except tk.TclError:
                pass
        self._krank_tooltip = tk.Toplevel(self)
        self._krank_tooltip.wm_overrideredirect(True)
        self._krank_tooltip.wm_geometry(f"+{x_root + 12}+{y_root + 12}")
        rahmen = tk.Frame(self._krank_tooltip, bg=Tagesansicht.KRANKRAND_AKZENT)
        rahmen.pack()
        tk.Label(
            rahmen,
            text=text,
            bg=Tagesansicht.KRANKRAND_AKZENT,
            fg="#1F1F1F",
            justify=tk.LEFT,
            anchor=tk.W,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        ).pack()

    def _krank_tooltip_verstecken(self) -> None:
        if self._krank_tooltip is not None:
            try:
                self._krank_tooltip.destroy()
            except tk.TclError:
                pass
        self._krank_tooltip = None

    def _monat_krank_balken_getroffen(
        self, canvas: tk.Canvas, tag: dt.date, x: float, y: float
    ) -> bool:
        if not ist_krankgeschrieben_am(tag):
            return False
        h = max(canvas.winfo_height(), 2)
        return y >= h - 9 and x >= 0

    def _monat_krank_mousemove(self, event: tk.Event, canvas: tk.Canvas, tag: dt.date) -> None:
        if self._monat_krank_balken_getroffen(canvas, tag, float(event.x), float(event.y)):
            text = self._krank_tooltip_text(tag)
            if text is not None:
                canvas.configure(cursor="hand2")
                self._krank_tooltip_anzeigen(text, int(event.x_root), int(event.y_root))
                return
        self._krank_tooltip_verstecken()
        canvas.configure(cursor="hand2")

    def _monat_krank_klick(self, event: tk.Event, canvas: tk.Canvas, tag: dt.date) -> bool:
        if not self._monat_krank_balken_getroffen(canvas, tag, float(event.x), float(event.y)):
            return False
        eintrag = eintrag_fuer_tag(tag)
        if eintrag is None:
            return False
        top = self.winfo_toplevel()
        setattr(top, "_ahds_krankmeldung_id", eintrag.id)
        try:
            top.event_generate("<<KrankmeldungOeffnen>>", when="tail")
        except tk.TclError:
            return False
        return True

    def _kw_nummer_binden(self, lb: tk.Label, ref_datum: dt.date) -> None:
        """Kalenderwoche anklicken → Wochenansicht (Anker: Referenztag der Rasterzeile)."""
        if self._on_kw_zeile is None:
            return
        lb.configure(cursor="hand2")
        lb.bind("<Button-1>", lambda e, d=ref_datum: self._on_kw_zeile(d))

        def _hover_enter(_e: tk.Event | None = None) -> None:
            kf = kalender_farben()
            lb.configure(
                bg=hex_rgb_mit_faktor(
                    kf.HINTERGRUND_ZEITLEISTE, MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR
                )
            )

        def _hover_leave(_e: tk.Event | None = None) -> None:
            kf = kalender_farben()
            lb.configure(bg=kf.HINTERGRUND_ZEITLEISTE)

        lb.bind("<Enter>", _hover_enter)
        lb.bind("<Leave>", _hover_leave)

    def _monat_tagzelle_klick_und_hover(
        self, fr: tk.Frame, w: tk.Canvas | tk.Label, tag: dt.date
    ) -> None:
        if isinstance(w, tk.Canvas):
            w.bind(
                "<Button-1>",
                lambda e, d=tag, cv=w: None
                if self._monat_krank_klick(e, cv, d)
                else self._klick_tag(d),
            )
            w.bind(
                "<Motion>",
                lambda e, d=tag, cv=w: self._monat_krank_mousemove(e, cv, d),
            )
            w.bind("<Leave>", lambda e: self._krank_tooltip_verstecken())
        else:
            w.bind("<Button-1>", lambda e, d=tag: self._klick_tag(d))
        w.bind("<Enter>", lambda e, f=fr, t=tag: self._monat_zelle_hover_enter(f, t))
        w.bind("<Leave>", lambda e, f=fr, t=tag: self._monat_zelle_hover_leave(f, t))

    def _monat_zelle_hover_enter(self, fr: tk.Frame, tag: dt.date) -> None:
        self._monat_zelle_hover_fr = fr
        kf = kalender_farben()
        farbe = _monat_hover_randfarbe(kf)
        fr.configure(
            highlightthickness=1,
            highlightbackground=farbe,
            highlightcolor=farbe,
        )

    def _monat_zelle_hover_leave(self, fr: tk.Frame, tag: dt.date) -> None:
        if self._monat_zelle_hover_fr is fr:
            self._monat_zelle_hover_fr = None
        heute = self._heute_datum()
        kf = kalender_farben()
        if tag == heute:
            fr.configure(
                highlightthickness=2,
                highlightbackground=kf.JETZT_ZEIGER,
                highlightcolor=kf.JETZT_ZEIGER,
            )
        else:
            fr.configure(highlightthickness=0)

    def _monats_wochentag_zelle_zeichnen(self, cv: tk.Canvas, tag: dt.date) -> None:
        """Stundenraster wie in der Streifen-Zeitleiste; Tagzahl oben rechts."""
        kf = kalender_farben()
        y, m = self._jahr, self._monat
        im_monat = tag.month == m and tag.year == y
        w = max(cv.winfo_width(), 2)
        h = max(cv.winfo_height(), 2)
        if w <= 2 or h <= 2:
            return
        cv.delete("all")
        if self._streifen_refs:
            self._streifen_refs[0].zeichne_monats_tag_zelle_zeitbereiche(
                cv, tag, w, h, kf
            )
        else:
            cv.configure(bg=kf.HINTERGRUND_BLATT)
        for yy in Tagesansicht.monats_wochentag_stundenlinien_y(h):
            cv.create_line(0, yy, w, yy, fill=kf.RASTER_STUNDE, width=1)
        fg = kf.TEXT_ZEIT if im_monat else kf.RASTER_STUNDE
        pad = 10
        cv.create_text(
            w - pad,
            pad,
            text=str(tag.day),
            anchor=tk.NE,
            fill=fg,
            font=("Segoe UI", 11),
        )
        if ist_krankgeschrieben_am(tag):
            cv.create_rectangle(
                0,
                h - 9,
                w,
                h,
                fill=Tagesansicht.KRANKRAND_FARBE,
                width=0,
                outline="",
            )
            cv.create_rectangle(
                0,
                h - 9,
                w,
                h - 6,
                fill=Tagesansicht.KRANKRAND_AKZENT,
                width=0,
                outline="",
            )
        if ist_wiedervorstellung_am(tag):
            radius = 8
            cx = 10
            cy = 10
            cv.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=Tagesansicht.ARZT_MARKER_FARBE,
                outline=Tagesansicht.ARZT_MARKER_FARBE,
                width=1,
            )
            cv.create_text(
                cx,
                cy,
                text=Tagesansicht.ARZT_MARKER_TEXT,
                fill="#FFFFFF",
                font=("Segoe UI", 7, "bold"),
            )
        if tag == self._heute_datum() and self._streifen_refs:
            tv = self._streifen_refs[0]
            tz = tv._standort_tz
            jetzt = dt.datetime.now(tz)
            if jetzt.date() == tag:
                mitternacht = dt.datetime.combine(tag, dt.time(0, 0), tzinfo=tz)
                minuten = (jetzt - mitternacht).total_seconds() / 60.0
                minuten = max(0.0, min(24.0 * 60.0, minuten))
                y0 = float(Tagesansicht.RAND_OBEN)
                y1 = float(h) - float(Tagesansicht.RAND_UNTEN)
                h_innen = max(y1 - y0, 1.0)
                y_j = y0 + (minuten / (24.0 * 60.0)) * h_innen
                tv._zeichnen_jetzt_zeiger(
                    cv,
                    kf,
                    0,
                    w,
                    jetzt,
                    y_mitte=y_j,
                    kompakt_banner=True,
                )
                tv._jetzt_zeiger_nach_oben(cv)

    def _zellen_malen(self) -> None:
        kf = kalender_farben()
        y, m = self._jahr, self._monat
        start = _erster_raster_tag(y, m, self._wochenstart)
        n_zeilen = _raster_zeilen(start, y, m)
        heute = self._heute_datum()
        hover_fr = self._monat_zelle_hover_fr
        hover_farbe = _monat_hover_randfarbe(kf) if hover_fr is not None else None
        i = 0
        for z in range(n_zeilen):
            for c in range(7):
                tag = start + dt.timedelta(days=z * 7 + c)
                fr, w, _ = self._zellen_refs[i]
                i += 1
                im_monat = tag.month == m and tag.year == y
                if self._rand is KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT and (
                    not im_monat
                ):
                    fr.configure(
                        bg=kf.HINTERGRUND_ZEITLEISTE,
                        highlightthickness=0,
                    )
                    continue
                if fr is hover_fr and hover_farbe is not None:
                    fr.configure(
                        highlightthickness=1,
                        highlightbackground=hover_farbe,
                        highlightcolor=hover_farbe,
                    )
                elif tag == heute:
                    fr.configure(
                        highlightthickness=2,
                        highlightbackground=kf.JETZT_ZEIGER,
                        highlightcolor=kf.JETZT_ZEIGER,
                    )
                else:
                    fr.configure(highlightthickness=0)
                if w is None:
                    continue
                if isinstance(w, tk.Canvas):
                    self._monats_wochentag_zelle_zeichnen(w, tag)
                else:
                    fr.configure(bg=kf.HINTERGRUND_BLATT)
                    w.configure(
                        bg=kf.HINTERGRUND_BLATT,
                        fg=kf.TEXT_ZEIT if im_monat else kf.RASTER_STUNDE,
                    )
