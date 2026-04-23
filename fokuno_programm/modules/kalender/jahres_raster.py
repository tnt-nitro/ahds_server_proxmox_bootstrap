"""Jahresübersicht: zwölf Monatsminikalender im Raster 4×3 (Jan–März erste Zeile usw.)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from zoneinfo import ZoneInfo
import tkinter as tk
from typing import Any

from locales import get_string

from modules.krankmeldung.speicher import (
    eintrag_fuer_tag,
    ist_krankgeschrieben_am,
    ist_wiedervorstellung_am,
)
from modules.sonnenzeit.standort import standard_frankfurt_am_main
from modules.theming.farben import kalender_farben

from .farb_hilfen import MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR, hex_rgb_mit_faktor
from .monats_raster import (
    KalenderMonatRanddarstellung,
    KalenderMonatWochenstart,
    _erster_raster_tag,
    _iso_kw_nummer,
    _mittwoch_referenztag,
    _montag_der_iso_woche_mit_tag,
    _monat_hover_randfarbe,
    _raster_zeilen,
    _wochentag_spalten_indices,
)
from .tagesansicht import Tagesansicht


class JahresRasterAnsicht(tk.Frame):
    """Ein Kalenderjahr als kompakte Übersicht (pro Monat Kurz-Wochentage + Tagzahlen)."""

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
        on_monat_titel: Callable[[dt.date], None] | None = None,
        on_kw_zeile: Callable[[dt.date], None] | None = None,
        transpose: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._locale = locale
        self._on_tag = on_tag
        self._on_tag_einzelansicht = on_tag_einzelansicht
        self._on_monat_titel = on_monat_titel
        self._on_kw_zeile = on_kw_zeile
        self._wochenstart = wochenstart
        self._rand = rand
        self._transpose = transpose
        self._jahr = mitte.year
        self._zellen_refs: list[
            tuple[tk.Frame, tk.Label | tk.Canvas | None, dt.date, int]
        ] = []
        self._kw_labels: list[tk.Label] = []
        self._jahres_jetzt_id: str | None = None
        #: Tagzelle unter der Maus (Rahmen; Jetzt-Zeiger auf Canvas unverändert).
        self._jahr_zelle_hover_fr: tk.Frame | None = None
        self._krank_tooltip: tk.Toplevel | None = None
        self._standort_tz: ZoneInfo = ZoneInfo(
            standard_frankfurt_am_main().zeitzone
        )
        self._outer = tk.Frame(self, bd=0, highlightthickness=0)
        self._outer.pack(fill=tk.BOTH, expand=True)
        self._aufbauen()

    def destroy(self) -> None:
        if self._jahres_jetzt_id is not None:
            try:
                self.after_cancel(self._jahres_jetzt_id)
            except tk.TclError:
                pass
            self._jahres_jetzt_id = None
        super().destroy()

    @property
    def jahr(self) -> int:
        return self._jahr

    def jahr_setzen(self, mitte: dt.date) -> None:
        if mitte.year == self._jahr:
            self.darstellung_auffrischen()
            return
        self._jahr = mitte.year
        self._aufbauen()

    def wochenstart_setzen(self, ws: KalenderMonatWochenstart) -> None:
        if ws is self._wochenstart:
            return
        self._wochenstart = ws
        self._aufbauen()

    def randdarstellung_setzen(self, r: KalenderMonatRanddarstellung) -> None:
        if r is self._rand:
            return
        self._rand = r
        self._aufbauen()

    def transpose_setzen(self, transponiert: bool) -> None:
        if transponiert is self._transpose:
            return
        self._transpose = transponiert
        self._aufbauen()

    def darstellung_auffrischen(self) -> None:
        self._zellen_malen()
        self._kw_spalte_farben()

    def _kw_spalte_farben(self) -> None:
        kf = kalender_farben()
        for lb in self._kw_labels:
            lb.configure(bg=kf.HINTERGRUND_ZEITLEISTE, fg=kf.TEXT_ZEIT)

    def layout_nach_elterngroesse(self) -> None:
        self.update_idletasks()
        self._outer.update_idletasks()
        try:
            self.pack_configure(fill=tk.BOTH, expand=True)
        except tk.TclError:
            pass

    def _klick_tag(self, d: dt.date) -> None:
        if self._on_tag_einzelansicht is not None:
            self._on_tag_einzelansicht(d)
            return
        if self._on_tag is not None:
            self._on_tag(d)

    def _zeitleiste_label_hover_binden(self, lb: tk.Label) -> None:
        def _enter(_e: tk.Event | None = None) -> None:
            kf = kalender_farben()
            lb.configure(
                bg=hex_rgb_mit_faktor(
                    kf.HINTERGRUND_ZEITLEISTE, MEHRTAG_KOPF_HOVER_DUNKEL_FAKTOR
                )
            )

        def _leave(_e: tk.Event | None = None) -> None:
            kf = kalender_farben()
            lb.configure(bg=kf.HINTERGRUND_ZEITLEISTE)

        lb.bind("<Enter>", _enter)
        lb.bind("<Leave>", _leave)

    def _jahr_monat_titel_binden(self, lb: tk.Label, erster: dt.date) -> None:
        if self._on_monat_titel is None:
            return
        lb.configure(cursor="hand2")
        lb.bind("<Button-1>", lambda e, d=erster: self._on_monat_titel(d))
        self._zeitleiste_label_hover_binden(lb)

    def _jahr_kw_nummer_binden(self, lb: tk.Label, ref_datum: dt.date) -> None:
        if self._on_kw_zeile is None:
            return
        lb.configure(cursor="hand2")
        lb.bind("<Button-1>", lambda e, d=ref_datum: self._on_kw_zeile(d))
        self._zeitleiste_label_hover_binden(lb)

    def _jahr_tagzelle_klick_und_hover(
        self, fr: tk.Frame, w: tk.Canvas | tk.Label, tag: dt.date
    ) -> None:
        if isinstance(w, tk.Canvas):
            w.bind(
                "<Button-1>",
                lambda e, d=tag, cv=w: None
                if self._jahr_krank_klick(e, cv, d)
                else self._klick_tag(d),
            )
            w.bind(
                "<Motion>",
                lambda e, d=tag, cv=w: self._jahr_krank_mousemove(e, cv, d),
            )
            w.bind("<Leave>", lambda e: self._krank_tooltip_verstecken())
        else:
            w.bind("<Button-1>", lambda e, d=tag: self._klick_tag(d))
        w.bind("<Enter>", lambda e, f=fr, t=tag: self._jahr_tag_hover_enter(f, t))
        w.bind("<Leave>", lambda e, f=fr, t=tag: self._jahr_tag_hover_leave(f, t))

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
        self._krank_tooltip_verstecken()
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
            font=("Segoe UI", 8),
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

    def _jahr_krank_balken_getroffen(
        self, canvas: tk.Canvas, tag: dt.date, x: float, y: float
    ) -> bool:
        if not ist_krankgeschrieben_am(tag):
            return False
        h = max(canvas.winfo_height(), 2)
        return y >= h - 6 and x >= 0

    def _jahr_krank_mousemove(self, event: tk.Event, canvas: tk.Canvas, tag: dt.date) -> None:
        if self._jahr_krank_balken_getroffen(canvas, tag, float(event.x), float(event.y)):
            text = self._krank_tooltip_text(tag)
            if text is not None:
                canvas.configure(cursor="hand2")
                self._krank_tooltip_anzeigen(text, int(event.x_root), int(event.y_root))
                return
        self._krank_tooltip_verstecken()
        canvas.configure(cursor="hand2")

    def _jahr_krank_klick(self, event: tk.Event, canvas: tk.Canvas, tag: dt.date) -> bool:
        if not self._jahr_krank_balken_getroffen(canvas, tag, float(event.x), float(event.y)):
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

    def _jahr_tag_hover_enter(self, fr: tk.Frame, tag: dt.date) -> None:
        self._jahr_zelle_hover_fr = fr
        kf = kalender_farben()
        farbe = _monat_hover_randfarbe(kf)
        fr.configure(
            highlightthickness=1,
            highlightbackground=farbe,
            highlightcolor=farbe,
        )

    def _jahr_tag_hover_leave(self, fr: tk.Frame, tag: dt.date) -> None:
        if self._jahr_zelle_hover_fr is fr:
            self._jahr_zelle_hover_fr = None
        heute = dt.date.today()
        kf = kalender_farben()
        if tag == heute:
            fr.configure(
                highlightthickness=2,
                highlightbackground=kf.JETZT_ZEIGER,
                highlightcolor=kf.JETZT_ZEIGER,
            )
        else:
            fr.configure(highlightthickness=0)

    def _plant_jahres_jetzt_tick(self) -> None:
        if self._jahres_jetzt_id is not None:
            try:
                self.after_cancel(self._jahres_jetzt_id)
            except tk.TclError:
                pass
            self._jahres_jetzt_id = None
        self._jahres_jetzt_id = self.after(1000, self._jahres_jetzt_tick)

    def _jahres_jetzt_tick(self) -> None:
        self._jahres_jetzt_id = None
        if not self.winfo_ismapped():
            return
        heute = dt.datetime.now(self._standort_tz).date()
        for fr, w, tag, monat in self._zellen_refs:
            if tag == heute and isinstance(w, tk.Canvas):
                try:
                    self._jahres_heute_zelle_zeichnen(w, tag, monat)
                except tk.TclError:
                    return
                break
        self._plant_jahres_jetzt_tick()

    def _jahres_heute_zelle_zeichnen(
        self, c: tk.Canvas, tag: dt.date, monat: int
    ) -> None:
        kf = kalender_farben()
        w = max(c.winfo_width(), 2)
        h = max(c.winfo_height(), 2)
        if w <= 2 or h <= 2:
            return
        c.delete("all")
        c.configure(bg=kf.HINTERGRUND_BLATT)
        y_j = self._jahr
        im_monat = tag.month == monat and tag.year == y_j
        c.create_rectangle(0, 0, w, h, fill=kf.HINTERGRUND_BLATT, width=0, outline="")
        fg = kf.TEXT_ZEIT if im_monat else kf.RASTER_STUNDE
        pad = 6
        c.create_text(
            w - pad,
            pad,
            text=str(tag.day),
            anchor=tk.NE,
            fill=fg,
            font=("Segoe UI", 8),
        )
        if ist_krankgeschrieben_am(tag):
            c.create_rectangle(
                0,
                h - 6,
                w,
                h,
                fill=Tagesansicht.KRANKRAND_FARBE,
                width=0,
                outline="",
            )
            c.create_rectangle(
                0,
                h - 6,
                w,
                h - 4,
                fill=Tagesansicht.KRANKRAND_AKZENT,
                width=0,
                outline="",
            )
        if ist_wiedervorstellung_am(tag):
            radius = 6
            cx = 8
            cy = 8
            c.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=Tagesansicht.ARZT_MARKER_FARBE,
                outline=Tagesansicht.ARZT_MARKER_FARBE,
                width=1,
            )
            c.create_text(
                cx,
                cy,
                text=Tagesansicht.ARZT_MARKER_TEXT,
                fill="#FFFFFF",
                font=("Segoe UI", 6, "bold"),
            )
        jetzt = dt.datetime.now(self._standort_tz)
        if jetzt.date() == tag:
            Tagesansicht.zeichne_jetzt_linie_in_tag_raster(
                c, kf, w, h, jetzt, tag, self._standort_tz
            )
            try:
                c.tag_raise(Tagesansicht.JETZT_CANVAS_TAG)
            except tk.TclError:
                pass

    def _tag_grid_spalte(self, wochentag_index_in_zeile: int) -> int:
        """Grid-Spalte für den ``wochentag_index_in_zeile``-ten Tag der Zeile (0…6)."""
        if self._wochenstart is KalenderMonatWochenstart.MONTAG:
            return 1 + wochentag_index_in_zeile
        return 0 if wochentag_index_in_zeile == 0 else wochentag_index_in_zeile + 1

    def _jahr_fill_mini_monat_transponiert(
        self,
        inner: tk.Frame,
        monat: int,
        y: int,
        heute: dt.date,
        kf: Any,
        idx: tuple[int, ...],
        linie: int,
        font_tag: tuple[Any, ...],
        font_head: tuple[Any, ...],
        font_kw: tuple[Any, ...],
    ) -> None:
        """Wochen als Spalten, Wochentage als Zeilen (wie Monatsraster transponiert)."""
        start = _erster_raster_tag(y, monat, self._wochenstart)
        n_zeilen = _raster_zeilen(start, y, monat)

        inner.grid_columnconfigure(0, weight=0, minsize=22)
        for wi in range(n_zeilen):
            inner.grid_columnconfigure(wi + 1, weight=1, uniform=f"jm{monat}")
        inner.grid_rowconfigure(0, weight=0, minsize=0)
        inner.grid_rowconfigure(1, weight=0, minsize=0)
        for r in range(7):
            inner.grid_rowconfigure(
                r + 2,
                weight=1,
                uniform=f"jmrow{monat}",
                minsize=0,
            )

        ecke = tk.Label(
            inner,
            text="",
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            font=font_head,
            bd=0,
            highlightthickness=0,
        )
        ecke.grid(row=1, column=0, sticky="nsew", padx=(linie, linie), pady=(linie, linie))
        self._kw_labels.append(ecke)

        for z in range(n_zeilen):
            zeilen_anfang = start + dt.timedelta(days=z * 7)
            kw_nr = _iso_kw_nummer(_montag_der_iso_woche_mit_tag(zeilen_anfang))
            h_kw = tk.Label(
                inner,
                text=f"{kw_nr:02d}",
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=font_kw,
                bd=0,
                highlightthickness=0,
            )
            h_kw.grid(
                row=1,
                column=z + 1,
                sticky="nsew",
                padx=(0, linie),
                pady=(linie, linie),
            )
            self._kw_labels.append(h_kw)
            ref_woche = _mittwoch_referenztag(start, z, self._wochenstart)
            self._jahr_kw_nummer_binden(h_kw, ref_woche)

        for c in range(7):
            wd = idx[c]
            lb_wt = tk.Label(
                inner,
                text=get_string(f"kalender.wochentag_kurz.{wd}", self._locale),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=font_head,
                bd=0,
                highlightthickness=0,
            )
            lb_wt.grid(
                row=c + 2,
                column=0,
                sticky="nsew",
                padx=(linie, linie),
                pady=(0, linie),
            )
            self._kw_labels.append(lb_wt)

        for z in range(n_zeilen):
            for c in range(7):
                tag = start + dt.timedelta(days=z * 7 + c)
                fr = tk.Frame(
                    inner,
                    bd=0,
                    highlightthickness=0,
                    bg=kf.HINTERGRUND_BLATT,
                )
                fr.grid(
                    row=c + 2,
                    column=z + 1,
                    sticky="nsew",
                    padx=(0, linie),
                    pady=(0, linie),
                )
                im_monat = tag.month == monat and tag.year == y
                if self._rand is KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT and (
                    not im_monat
                ):
                    fr.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
                    self._zellen_refs.append((fr, None, tag, monat))
                    continue
                cursor_zelle = (
                    "hand2"
                    if im_monat
                    or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                    else "arrow"
                )
                if tag == heute:
                    cv_heute = tk.Canvas(
                        fr,
                        highlightthickness=0,
                        bd=0,
                        bg=kf.HINTERGRUND_BLATT,
                        cursor=cursor_zelle,
                    )
                    cv_heute.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)
                    cv_heute.bind(
                        "<Configure>",
                        lambda e, cv=cv_heute, t=tag, m=monat: self._jahres_heute_zelle_zeichnen(
                            cv, t, m
                        ),
                    )
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._jahr_tagzelle_klick_und_hover(fr, cv_heute, tag)
                    fr.configure(
                        highlightthickness=2,
                        highlightbackground=kf.JETZT_ZEIGER,
                    )
                    self._zellen_refs.append((fr, cv_heute, tag, monat))
                else:
                    tl = tk.Label(
                        fr,
                        text=str(tag.day),
                        bg=kf.HINTERGRUND_BLATT,
                        fg=kf.TEXT_ZEIT,
                        font=font_tag,
                        bd=0,
                        highlightthickness=0,
                        cursor=cursor_zelle,
                    )
                    tl.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)
                    if not im_monat:
                        tl.configure(fg=kf.RASTER_STUNDE)
                    if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                        self._jahr_tagzelle_klick_und_hover(fr, tl, tag)
                    self._zellen_refs.append((fr, tl, tag, monat))

    def _aufbauen(self) -> None:
        if self._jahres_jetzt_id is not None:
            try:
                self.after_cancel(self._jahres_jetzt_id)
            except tk.TclError:
                pass
            self._jahres_jetzt_id = None
        for w in self._outer.winfo_children():
            w.destroy()
        self._zellen_refs.clear()
        self._kw_labels.clear()
        self._jahr_zelle_hover_fr = None
        kf = kalender_farben()
        linie = 1
        self._outer.configure(bg=kf.RASTER_STUNDE)
        for r in range(6):
            self._outer.grid_rowconfigure(r, weight=0, uniform="")
        for c in range(6):
            self._outer.grid_columnconfigure(c, weight=0, uniform="")
        if self._transpose:
            for r in range(3):
                self._outer.grid_rowconfigure(r, weight=1, uniform="jahr_zeile")
            for c in range(4):
                self._outer.grid_columnconfigure(c, weight=1, uniform="jahr_spalte")
        else:
            for r in range(4):
                self._outer.grid_rowconfigure(r, weight=1, uniform="jahr_zeile")
            for c in range(3):
                self._outer.grid_columnconfigure(c, weight=1, uniform="jahr_spalte")

        heute = dt.date.today()
        idx = _wochentag_spalten_indices(self._wochenstart)
        y = self._jahr
        font_tag = ("Segoe UI", 8)
        font_head = ("Segoe UI", 7, "bold")
        font_titel = ("Segoe UI", 9, "bold")
        font_kw = ("Segoe UI", 7, "bold")

        kw_kopf_text = get_string("kalender.raster_kw_spalte", self._locale)
        kw_spalte_cfg = dict(weight=0, minsize=22)

        for monat in range(1, 13):
            if self._transpose:
                gr = (monat - 1) // 4
                gc = (monat - 1) % 4
            else:
                gr = (monat - 1) // 3
                gc = (monat - 1) % 3
            block = tk.Frame(self._outer, bd=0, highlightthickness=0, bg=kf.RASTER_STUNDE)
            block.grid(
                row=gr,
                column=gc,
                sticky="nsew",
                padx=(linie, linie),
                pady=(linie, linie),
            )
            inner = tk.Frame(block, bd=0, highlightthickness=0, bg=kf.HINTERGRUND_BLATT)
            inner.pack(fill=tk.BOTH, expand=True, padx=linie, pady=linie)
            start = _erster_raster_tag(y, monat, self._wochenstart)
            n_zeilen = _raster_zeilen(start, y, monat)
            titel = tk.Label(
                inner,
                text=get_string(f"kalender.monat_lang.{monat}", self._locale),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=font_titel,
                bd=0,
                highlightthickness=0,
                padx=4,
                pady=2,
            )
            titel.grid(
                row=0,
                column=0,
                columnspan=(n_zeilen + 1) if self._transpose else 8,
                sticky="ew",
            )
            self._jahr_monat_titel_binden(titel, dt.date(y, monat, 1))

            if self._transpose:
                self._jahr_fill_mini_monat_transponiert(
                    inner,
                    monat,
                    y,
                    heute,
                    kf,
                    idx,
                    linie,
                    font_tag,
                    font_head,
                    font_kw,
                )
                continue

            if self._wochenstart is KalenderMonatWochenstart.MONTAG:
                inner.grid_columnconfigure(0, **kw_spalte_cfg)
                for ci in range(7):
                    inner.grid_columnconfigure(1 + ci, weight=1, uniform=f"jm{monat}")
                kw_h = tk.Label(
                    inner,
                    text=kw_kopf_text,
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=font_head,
                    bd=0,
                    highlightthickness=0,
                )
                kw_h.grid(row=1, column=0, sticky="nsew", padx=(linie, linie), pady=(linie, 0))
                self._kw_labels.append(kw_h)
                for ci in range(7):
                    wd = idx[ci]
                    h = tk.Label(
                        inner,
                        text=get_string(f"kalender.wochentag_kurz.{wd}", self._locale),
                        bg=kf.HINTERGRUND_ZEITLEISTE,
                        fg=kf.TEXT_ZEIT,
                        font=font_head,
                        bd=0,
                        highlightthickness=0,
                    )
                    h.grid(
                        row=1,
                        column=1 + ci,
                        sticky="nsew",
                        padx=(0, linie),
                        pady=(linie, 0),
                    )
            else:
                inner.grid_columnconfigure(0, weight=1, uniform=f"jm{monat}")
                inner.grid_columnconfigure(1, **kw_spalte_cfg)
                for ci in range(6):
                    inner.grid_columnconfigure(2 + ci, weight=1, uniform=f"jm{monat}")
                wd0 = idx[0]
                h0 = tk.Label(
                    inner,
                    text=get_string(f"kalender.wochentag_kurz.{wd0}", self._locale),
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=font_head,
                    bd=0,
                    highlightthickness=0,
                )
                h0.grid(row=1, column=0, sticky="nsew", padx=(linie, 0), pady=(linie, 0))
                kw_h = tk.Label(
                    inner,
                    text=kw_kopf_text,
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=font_head,
                    bd=0,
                    highlightthickness=0,
                )
                kw_h.grid(row=1, column=1, sticky="nsew", padx=(0, linie), pady=(linie, 0))
                self._kw_labels.append(kw_h)
                for j in range(1, 7):
                    wd = idx[j]
                    h = tk.Label(
                        inner,
                        text=get_string(f"kalender.wochentag_kurz.{wd}", self._locale),
                        bg=kf.HINTERGRUND_ZEITLEISTE,
                        fg=kf.TEXT_ZEIT,
                        font=font_head,
                        bd=0,
                        highlightthickness=0,
                    )
                    h.grid(
                        row=1,
                        column=1 + j,
                        sticky="nsew",
                        padx=(0, linie),
                        pady=(linie, 0),
                    )

            inner.grid_rowconfigure(0, weight=0, minsize=0)
            inner.grid_rowconfigure(1, weight=0, minsize=0)
            for zz in range(n_zeilen):
                inner.grid_rowconfigure(
                    zz + 2,
                    weight=1,
                    uniform=f"jmrow{monat}",
                    minsize=0,
                )

            for z in range(n_zeilen):
                zeilen_anfang = start + dt.timedelta(days=z * 7)
                kw_nr = _iso_kw_nummer(_montag_der_iso_woche_mit_tag(zeilen_anfang))
                if self._wochenstart is KalenderMonatWochenstart.MONTAG:
                    kw_col_grid = 0
                else:
                    kw_col_grid = 1
                kw_lab = tk.Label(
                    inner,
                    text=f"{kw_nr:02d}",
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=font_kw,
                    bd=0,
                    highlightthickness=0,
                )
                kw_lab.grid(
                    row=z + 2,
                    column=kw_col_grid,
                    sticky="nsew",
                    padx=(linie, linie),
                    pady=(0, linie),
                )
                self._kw_labels.append(kw_lab)
                ref_woche = _mittwoch_referenztag(start, z, self._wochenstart)
                self._jahr_kw_nummer_binden(kw_lab, ref_woche)

                for ci in range(7):
                    tag = start + dt.timedelta(days=z * 7 + ci)
                    gcol = self._tag_grid_spalte(ci)
                    fr = tk.Frame(
                        inner,
                        bd=0,
                        highlightthickness=0,
                        bg=kf.HINTERGRUND_BLATT,
                    )
                    fr.grid(
                        row=z + 2,
                        column=gcol,
                        sticky="nsew",
                        padx=(0 if gcol > 0 else linie, linie),
                        pady=(0, linie),
                    )
                    im_monat = tag.month == monat and tag.year == y
                    if self._rand is KalenderMonatRanddarstellung.NUR_AKTUELLER_MONAT and (
                        not im_monat
                    ):
                        fr.configure(bg=kf.HINTERGRUND_ZEITLEISTE)
                        self._zellen_refs.append((fr, None, tag, monat))
                        continue
                    cursor_zelle = (
                        "hand2"
                        if im_monat
                        or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN
                        else "arrow"
                    )
                    if tag == heute:
                        cv_heute = tk.Canvas(
                            fr,
                            highlightthickness=0,
                            bd=0,
                            bg=kf.HINTERGRUND_BLATT,
                            cursor=cursor_zelle,
                        )
                        cv_heute.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)
                        cv_heute.bind(
                            "<Configure>",
                            lambda e, cv=cv_heute, t=tag, m=monat: self._jahres_heute_zelle_zeichnen(
                                cv, t, m
                            ),
                        )
                        if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                            self._jahr_tagzelle_klick_und_hover(fr, cv_heute, tag)
                        fr.configure(
                            highlightthickness=2,
                            highlightbackground=kf.JETZT_ZEIGER,
                        )
                        self._zellen_refs.append((fr, cv_heute, tag, monat))
                    else:
                        tl = tk.Label(
                            fr,
                            text=str(tag.day),
                            bg=kf.HINTERGRUND_BLATT,
                            fg=kf.TEXT_ZEIT,
                            font=font_tag,
                            bd=0,
                            highlightthickness=0,
                            cursor=cursor_zelle,
                        )
                        tl.pack(expand=True, fill=tk.BOTH, padx=1, pady=1)
                        if not im_monat:
                            tl.configure(fg=kf.RASTER_STUNDE)
                        if im_monat or self._rand is KalenderMonatRanddarstellung.MIT_RANDMONAT_TAGEN:
                            self._jahr_tagzelle_klick_und_hover(fr, tl, tag)
                        self._zellen_refs.append((fr, tl, tag, monat))
        self._zellen_malen()
        if any(tag == heute for _, w, tag, _ in self._zellen_refs if w is not None):
            self._plant_jahres_jetzt_tick()
        self.after_idle(self.layout_nach_elterngroesse)
        self.after(100, self.layout_nach_elterngroesse)

    def _zellen_malen(self) -> None:
        kf = kalender_farben()
        heute = dt.date.today()
        y = self._jahr
        hover_fr = self._jahr_zelle_hover_fr
        hover_farbe = _monat_hover_randfarbe(kf) if hover_fr is not None else None
        for fr, w, tag, monat in self._zellen_refs:
            im_monat = tag.month == monat and tag.year == y
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
            fr.configure(bg=kf.HINTERGRUND_BLATT)
            if isinstance(w, tk.Canvas):
                self._jahres_heute_zelle_zeichnen(w, tag, monat)
                continue
            w.configure(
                bg=kf.HINTERGRUND_BLATT,
                fg=kf.TEXT_ZEIT if im_monat else kf.RASTER_STUNDE,
            )
