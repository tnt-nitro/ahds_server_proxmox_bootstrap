"""Kompakter Monatskalender für die Toolbox."""

from __future__ import annotations

import calendar
import datetime as dt
import tkinter as tk
from collections.abc import Callable
from zoneinfo import ZoneInfo

from locales import get_string
from modules.kalender.tagesansicht import Tagesansicht
from modules.sonnenzeit.standort import standard_frankfurt_am_main
from modules.theming.farben import kalender_farben
from modules.userzeit.wachzeit import standard_wachzeit


def _titel_monat_jahr(datum: dt.date, locale: str) -> str:
    monat = get_string(f"kalender.monat_lang.{datum.month}", locale)
    return f"{monat} {datum.year}"


def _iso_kw_montag(woche: list[dt.date]) -> int:
    """ISO-KW-Nummer für die Woche (Liste startet am Montag)."""
    return int(woche[0].isocalendar()[1])


def _jetzt_linie_kompakt_vollhoehe(
    canvas: tk.Canvas,
    kf,
    breite: int,
    hoehe: int,
    jetzt: dt.datetime,
    tag: dt.date,
    tz: ZoneInfo,
) -> None:
    """Jetzt-Linie wie ``zeichne_jetzt_linie_in_tag_raster``, aber ohne RAND_OBEN/UNTEN.

    Die Mini-Zelle mappt 0:00–24:00 auf die volle Canvas-Höhe; die Standard-Methode
    nutzt dagegen die Ränder der großen Monatszelle und würde die Linie verschieben.
    """
    if jetzt.date() != tag:
        return
    y0 = 0.0
    y1 = float(hoehe)
    h_innen = max(y1 - y0, 1.0)
    mitternacht = dt.datetime.combine(tag, dt.time(0, 0), tzinfo=tz)
    minuten = (jetzt - mitternacht).total_seconds() / 60.0
    minuten = max(0.0, min(24.0 * 60.0, minuten))
    y_linie = y0 + (minuten / (24.0 * 60.0)) * h_innen
    canvas.create_line(
        0,
        y_linie,
        breite,
        y_linie,
        fill=kf.JETZT_ZEIGER,
        width=1,
        tags=(Tagesansicht.JETZT_CANVAS_TAG,),
    )


def mini_monat_in(
    parent: tk.Misc,
    *,
    mitte_datum: dt.date,
    locale: str = "de",
    on_tag: Callable[[dt.date], None] | None = None,
    tag_stil_fn: Callable[[dt.date], dict[str, object] | None] | None = None,
) -> Callable[[dt.date], None]:
    """Rendert einen kompakten Monatskalender in ``parent`` und liefert Setter für Datum."""

    kf = kalender_farben()
    aussen = tk.Frame(
        parent,
        bg=kf.HINTERGRUND_BLATT,
        highlightthickness=1,
        highlightbackground=kf.TRENNLINIE,
    )
    aussen.pack(fill=tk.X)

    kopf = tk.Frame(aussen, bg=kf.HINTERGRUND_BLATT)
    kopf.pack(fill=tk.X, padx=8, pady=(8, 4))
    kopf_zeile = tk.Frame(kopf, bg=kf.HINTERGRUND_BLATT)
    kopf_zeile.pack(fill=tk.X)
    titel = tk.Label(
        kopf_zeile,
        bg=kf.HINTERGRUND_BLATT,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 11, "bold"),
        anchor=tk.W,
    )
    titel.pack(side=tk.LEFT, fill=tk.X, expand=True)

    transpose_var = tk.BooleanVar(master=kopf, value=False)
    _SYM_ACHSE = "\u21C4"  # ⇄

    def _achsen_btn_theme() -> None:
        """Gleiches Erscheinungsbild in beiden Zuständen (kein „aktiv“-Einfärben)."""
        kfa = kalender_farben()
        btn_achse.configure(
            bg=kfa.HINTERGRUND_BLATT,
            fg=kfa.TEXT_ZEIT,
            activebackground=kfa.RASTER_STUNDE,
            activeforeground=kfa.TEXT_ZEIT,
        )

    btn_achse = tk.Button(
        kopf_zeile,
        text=_SYM_ACHSE,
        font=("Segoe UI", 12),
        width=2,
        height=1,
        relief=tk.FLAT,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
        command=lambda: None,
    )
    btn_achse.pack(side=tk.RIGHT, anchor=tk.NE)

    class _MiniToolTip:
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

    _MiniToolTip(
        btn_achse,
        get_string("app.minikalender.achsen_tooltip", locale),
    )

    raster = tk.Frame(aussen, bg=kf.HINTERGRUND_BLATT)
    raster.pack(fill=tk.X, padx=8, pady=(0, 8))

    tag_widgets: list[tk.Widget] = []
    heute_canvas_refs: list[tuple[tk.Canvas, dt.date, bool]] = []
    kw_labels: list[tk.Label] = []
    heutiger_tag = dt.date.today()
    sicht_datum = [mitte_datum]
    cal = calendar.Calendar(firstweekday=0)
    tick_id: list[str | None] = [None]
    standort_tz = ZoneInfo(standard_frankfurt_am_main().zeitzone)
    zeichenhilfe = Tagesansicht(
        aussen,
        mitte_datum,
        standard_wachzeit(),
        locale=locale,
        mit_zeitleiste_und_sonne=False,
        kalenderblatt_zeigen=True,
        periodisches_neuzeichnen=False,
    )

    # Einheitliche Zellhöhe: verhindert, dass einzelne Widgets die Zeilenhöhe aufblasen.
    _ZELL_H = 28
    _KOPF_H = 18

    def _stil_fuer_tag(tag: dt.date) -> dict[str, object]:
        if tag_stil_fn is None:
            return {}
        stil = tag_stil_fn(tag)
        if stil is None:
            return {}
        return dict(stil)

    def _zeichne_tagzelle(canvas: tk.Canvas, tag: dt.date, im_monat: bool) -> None:
        w = max(canvas.winfo_width(), 2)
        h = max(canvas.winfo_height(), 2)
        if w <= 2 or h <= 2:
            return
        canvas.delete("all")
        basis = kf.HINTERGRUND_BLATT if im_monat else kf.HINTERGRUND_ZEITLEISTE
        stil = _stil_fuer_tag(tag)
        zellen_hintergrund = str(stil.get("hintergrund", basis))
        bereich_markiert = bool(stil.get("bereich_markierung", False))
        alt_cache = zeichenhilfe._sichtbar_cache  # type: ignore[attr-defined]
        try:
            zeichenhilfe._monats_blatt_datum_override = tag  # type: ignore[attr-defined]
            zeichenhilfe._sichtbar_cache = (0.0, 24.0 * 60.0)  # type: ignore[attr-defined]
            y0 = 0.0
            h_innen = float(h)
            xk = 0.0
            x_rechts = float(w)
            pf = zeichenhilfe._phasen_farben_aktuell()  # type: ignore[attr-defined]
            canvas.create_rectangle(
                xk, y0, x_rechts, h_innen, fill=zellen_hintergrund, width=0
            )
            if not bereich_markiert:
                for m0, m1, ist_wach in zeichenhilfe._phasen_segmente_sichtbar():  # type: ignore[attr-defined]
                    fill = pf.wach_hex if ist_wach else pf.schlaf_hex
                    ya = zeichenhilfe._minute_nach_y(m0, h_innen, y0)  # type: ignore[attr-defined]
                    yb = zeichenhilfe._minute_nach_y(m1, h_innen, y0)  # type: ignore[attr-defined]
                    if yb < ya:
                        ya, yb = yb, ya
                    if yb - ya < 1.0:
                        yb = ya + 1.0
                    canvas.create_rectangle(xk, ya, x_rechts, yb, fill=fill, width=0)
                zeichenhilfe._zeichnen_regelarbeit_statisch(canvas, xk, x_rechts, y0, h_innen)  # type: ignore[attr-defined]
                zeichenhilfe._zeichnen_pausen_statisch(canvas, xk, x_rechts, y0, h_innen)  # type: ignore[attr-defined]
                zeichenhilfe._zeichnen_wegezeit_statisch(canvas, xk, x_rechts, y0, h_innen)  # type: ignore[attr-defined]
                zeichenhilfe._zeichnen_zeitaufzeichnung_statisch(canvas, xk, x_rechts, y0, h_innen)  # type: ignore[attr-defined]
        finally:
            zeichenhilfe._monats_blatt_datum_override = None  # type: ignore[attr-defined]
            zeichenhilfe._sichtbar_cache = alt_cache  # type: ignore[attr-defined]
        if bereich_markiert:
            bereich_farbe = str(stil.get("bereich_farbe", "#FFD966"))
            canvas.create_rectangle(
                0,
                0,
                float(w),
                float(h),
                fill=bereich_farbe,
                outline="",
            )
        fg = kf.TEXT_ZEIT if im_monat else kf.RASTER_STUNDE
        if "text_farbe" in stil:
            fg = str(stil["text_farbe"])
        ist_aktiv = tag == sicht_datum[0]
        if ist_aktiv:
            fg = kf.JETZT_ZEIGER
        canvas.create_text(
            w - 5,
            5,
            text=str(tag.day),
            anchor=tk.NE,
            fill=fg,
            font=("Segoe UI", 9),
        )
        marker_text = str(stil.get("marker_text", "")).strip()
        if marker_text:
            marker_farbe = str(stil.get("marker_farbe", "#245B9E"))
            marker_text_farbe = str(stil.get("marker_text_farbe", "#FFFFFF"))
            radius = 6
            cx = 7
            cy = 7
            canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=marker_farbe,
                outline=marker_farbe,
                width=1,
            )
            canvas.create_text(
                cx,
                cy,
                text=marker_text[:1],
                fill=marker_text_farbe,
                font=("Segoe UI", 7, "bold"),
                anchor=tk.CENTER,
            )
        if tag == dt.datetime.now(standort_tz).date():
            jetzt = dt.datetime.now(standort_tz)
            _jetzt_linie_kompakt_vollhoehe(canvas, kf, w, h, jetzt, tag, standort_tz)
            try:
                canvas.tag_raise(Tagesansicht.JETZT_CANVAS_TAG)
            except tk.TclError:
                pass

    def _klick(tag: dt.date) -> None:
        sicht_datum[0] = tag
        _render()
        if on_tag is not None:
            on_tag(tag)

    def _tag_zelle_einsetzen(
        grid_row: int,
        grid_col: int,
        tag: dt.date,
        im_monat: bool,
        *,
        padx_links: tuple[int, int] = (0, 0),
    ) -> None:
        basis = kf.HINTERGRUND_BLATT if im_monat else kf.HINTERGRUND_ZEITLEISTE
        stil = _stil_fuer_tag(tag)
        hintergrund = str(stil.get("hintergrund", basis)) if stil is not None else basis
        rahmen_dicke = 0
        rahmen_farbe = ""
        if tag == heutiger_tag:
            rahmen_dicke = 2
            rahmen_farbe = kf.JETZT_ZEIGER
        elif tag == sicht_datum[0]:
            rahmen_dicke = 1
            rahmen_farbe = kf.TRENNLINIE
        if "rahmen_dicke" in stil:
            try:
                rahmen_dicke = max(0, int(stil["rahmen_dicke"]))
            except (TypeError, ValueError):
                pass
        if "rahmen_farbe" in stil:
            rahmen_farbe = str(stil["rahmen_farbe"])
        zelle = tk.Frame(
            raster,
            bg=hintergrund,
            bd=0,
            highlightthickness=0,
            height=_ZELL_H,
        )
        if rahmen_dicke > 0:
            zelle.configure(
                highlightthickness=rahmen_dicke,
                highlightbackground=rahmen_farbe,
            )
        zelle.grid(
            row=grid_row,
            column=grid_col,
            sticky="nsew",
            padx=padx_links,
            pady=0,
        )
        zelle.pack_propagate(False)
        cv = tk.Canvas(
            zelle,
            bg=hintergrund,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        cv.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        cv.bind("<Button-1>", lambda e, d=tag: _klick(d))
        cv.bind(
            "<Configure>",
            lambda _e, canvas=cv, datum=tag, in_month=im_monat: _zeichne_tagzelle(
                canvas, datum, in_month
            ),
        )
        _zeichne_tagzelle(cv, tag, im_monat)
        heute_canvas_refs.append((cv, tag, im_monat))
        tag_widgets.append(zelle)

    def _render() -> None:
        nonlocal kf, heutiger_tag
        ist_transponiert = bool(transpose_var.get())
        kf = kalender_farben()
        heutiger_tag = dt.date.today()
        titel.configure(
            text=_titel_monat_jahr(sicht_datum[0], locale),
            bg=kf.HINTERGRUND_BLATT,
            fg=kf.TEXT_ZEIT,
        )
        _achsen_btn_theme()
        aussen.configure(bg=kf.HINTERGRUND_BLATT, highlightbackground=kf.TRENNLINIE)
        kopf.configure(bg=kf.HINTERGRUND_BLATT)
        kopf_zeile.configure(bg=kf.HINTERGRUND_BLATT)
        raster.configure(bg=kf.HINTERGRUND_BLATT)

        for w in raster.winfo_children():
            w.destroy()
        kw_labels.clear()
        tag_widgets.clear()
        heute_canvas_refs.clear()

        y = sicht_datum[0].year
        m = sicht_datum[0].month
        wochen = cal.monthdatescalendar(y, m)

        if ist_transponiert:
            n_kw = len(wochen)
            raster.grid_columnconfigure(0, weight=0, minsize=28)
            for wc in range(n_kw):
                raster.grid_columnconfigure(
                    wc + 1, weight=1, uniform="mini_kw_spalte"
                )
            raster.grid_rowconfigure(0, weight=0, minsize=_KOPF_H)
            for rr in range(1, 8):
                raster.grid_rowconfigure(rr, weight=0, minsize=_ZELL_H + 1)

            ecke = tk.Label(
                raster,
                text="",
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 8, "bold"),
                padx=0,
                pady=0,
            )
            ecke.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            kw_labels.append(ecke)

            for wi, woche in enumerate(wochen):
                kw_nr = _iso_kw_montag(woche)
                h_kw = tk.Label(
                    raster,
                    text=f"{kw_nr:02d}",
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=("Segoe UI", 8, "bold"),
                    padx=0,
                    pady=0,
                )
                h_kw.grid(
                    row=0,
                    column=wi + 1,
                    sticky="nsew",
                    padx=0,
                    pady=0,
                )
                kw_labels.append(h_kw)

            for wd in range(7):
                lb_wt = tk.Label(
                    raster,
                    text=get_string(f"kalender.wochentag_kurz.{wd}", locale),
                    bg=kf.HINTERGRUND_ZEITLEISTE,
                    fg=kf.TEXT_ZEIT,
                    font=("Segoe UI", 8, "bold"),
                    padx=0,
                    pady=0,
                )
                lb_wt.grid(
                    row=wd + 1,
                    column=0,
                    sticky="nsew",
                    padx=0,
                    pady=0,
                )
                kw_labels.append(lb_wt)

            for wi, woche in enumerate(wochen):
                for wd in range(7):
                    tag = woche[wd]
                    im_monat = tag.month == m
                    _tag_zelle_einsetzen(
                        wd + 1,
                        wi + 1,
                        tag,
                        im_monat,
                        padx_links=(0, 0),
                    )
            return

        # Standard: Wochen als Zeilen, Wochentage als Spalten
        raster.grid_columnconfigure(0, weight=0, minsize=28)
        for c in range(1, 8):
            raster.grid_columnconfigure(c, weight=1, uniform="mini_monat")
        for r in range(0, 8):
            raster.grid_rowconfigure(r, weight=0, minsize=0)
        raster.grid_rowconfigure(0, weight=0, minsize=_KOPF_H)
        for rr in range(1, 8):
            raster.grid_rowconfigure(rr, weight=0, minsize=_ZELL_H + 1)

        kw_kopf = tk.Label(
            raster,
            text=get_string("kalender.raster_kw_spalte", locale),
            bg=kf.HINTERGRUND_ZEITLEISTE,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 8, "bold"),
            padx=0,
            pady=0,
        )
        kw_kopf.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        kw_labels.append(kw_kopf)

        for c in range(7):
            lb = tk.Label(
                raster,
                text=get_string(f"kalender.wochentag_kurz.{c}", locale),
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 8, "bold"),
                padx=0,
                pady=0,
            )
            lb.grid(
                row=0,
                column=c + 1,
                sticky="nsew",
                padx=0,
                pady=0,
            )
            kw_labels.append(lb)

        row = 1
        for woche in wochen:
            kw_nr = _iso_kw_montag(woche)
            kw_zelle = tk.Frame(
                raster,
                bg=kf.HINTERGRUND_ZEITLEISTE,
                bd=0,
                highlightthickness=0,
                height=_ZELL_H,
            )
            kw_zelle.grid(row=row, column=0, sticky="nsew", padx=0, pady=0)
            kw_zelle.pack_propagate(False)
            kw_lb = tk.Label(
                kw_zelle,
                text=f"{kw_nr:02d}",
                bg=kf.HINTERGRUND_ZEITLEISTE,
                fg=kf.TEXT_ZEIT,
                font=("Segoe UI", 8, "bold"),
                padx=2,
                pady=0,
            )
            kw_lb.pack(fill=tk.BOTH, expand=True)
            kw_labels.append(kw_lb)
            for col, tag in enumerate(woche):
                im_monat = tag.month == m
                _tag_zelle_einsetzen(
                    row,
                    col + 1,
                    tag,
                    im_monat,
                    padx_links=(0, 0),
                )
            row += 1

    def _achsen_klick() -> None:
        transpose_var.set(not transpose_var.get())
        _render()

    btn_achse.configure(command=_achsen_klick)

    def datum_setzen(neu: dt.date) -> None:
        sicht_datum[0] = neu
        _render()

    def _tick() -> None:
        tick_id[0] = None
        for canvas, tag, im_monat in heute_canvas_refs:
            try:
                if tag == dt.datetime.now(standort_tz).date():
                    _zeichne_tagzelle(canvas, tag, im_monat)
            except tk.TclError:
                return
        tick_id[0] = aussen.after(1000, _tick)

    def _beim_destroy(_e: tk.Event) -> None:
        if tick_id[0] is not None:
            try:
                aussen.after_cancel(tick_id[0])
            except tk.TclError:
                pass
            tick_id[0] = None
        try:
            zeichenhilfe.destroy()
        except tk.TclError:
            pass

    _render()
    tick_id[0] = aussen.after(1000, _tick)
    aussen.bind("<Destroy>", _beim_destroy)
    return datum_setzen
