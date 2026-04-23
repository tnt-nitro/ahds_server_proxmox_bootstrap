"""Schnellbild: Live-Vorschau und Foto speichern (OpenCV + Tk)."""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

from locales import get_string
from modules.theming.farben import kalender_farben

try:
    import cv2
    from PIL import Image, ImageTk

    _BILD_OK = True
except ImportError:
    _BILD_OK = False

VORSCHAU_BREITE = 640
VORSCHAU_HOEHE = 480


def _speicher_ordner() -> Path:
    p = Path.home() / "AhDs" / "Schnellbilder"
    p.mkdir(parents=True, exist_ok=True)
    return p


def schnellbild_in(parent: tk.Misc, locale: str = "de") -> None:
    """Baut die Schnellbild-Ansicht in den übergebenen Container."""

    kf = kalender_farben()
    root = parent.winfo_toplevel()

    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    titel = tk.Label(
        aussen,
        text=get_string("app.schnellbild.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
    )
    titel.pack(anchor=tk.W)

    if not _BILD_OK:
        tk.Label(
            aussen,
            text=get_string("app.schnellbild.fehlende_abhaengigkeit", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 11),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))
        return

    unter = tk.Label(
        aussen,
        text=get_string("app.schnellbild.untertitel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        justify=tk.LEFT,
    )
    unter.pack(anchor=tk.W, pady=(4, 8))

    status = tk.Label(
        aussen,
        text=get_string("app.schnellbild.status_bereit", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
    )
    status.pack(anchor=tk.W, pady=(0, 8))

    vorschau_rahmen = tk.Frame(
        aussen,
        bg=kf.HINTERGRUND_BLATT,
        width=VORSCHAU_BREITE + 4,
        height=VORSCHAU_HOEHE + 4,
        highlightthickness=0,
        bd=0,
    )
    vorschau_rahmen.pack()
    vorschau_rahmen.pack_propagate(False)

    bild_label = tk.Label(
        vorschau_rahmen,
        bg=kf.HINTERGRUND_BLATT,
        width=VORSCHAU_BREITE,
        height=VORSCHAU_HOEHE,
    )
    bild_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    if sys.platform == "win32":
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        tk.Label(
            aussen,
            text=get_string("app.schnellbild.kamera_nicht_erreichbar", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 11),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    preview_laeuft = [True]
    after_id: list[int | None] = [None]
    letzter_frame: list[object | None] = [None]

    def btn_style() -> dict[str, object]:
        k = kalender_farben()
        return {
            "bg": k.HINTERGRUND_ZEITLEISTE,
            "fg": k.TEXT_ZEIT,
            "activebackground": k.RASTER_STUNDE,
            "activeforeground": k.TEXT_ZEIT,
            "font": ("Segoe UI", 10),
            "relief": tk.FLAT,
            "padx": 12,
            "pady": 6,
        }

    def einzelbild_aktualisieren() -> None:
        if not preview_laeuft[0]:
            return
        ok, frame = cap.read()
        if not ok:
            after_id[0] = root.after(50, einzelbild_aktualisieren)
            return
        letzter_frame[0] = frame.copy()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        skal = min(VORSCHAU_BREITE / w, VORSCHAU_HOEHE / h)
        neu_w = max(1, int(w * skal))
        neu_h = max(1, int(h * skal))
        klein = cv2.resize(rgb, (neu_w, neu_h), interpolation=cv2.INTER_AREA)
        im = Image.fromarray(klein)
        photo = ImageTk.PhotoImage(image=im)
        bild_label.configure(image=photo)
        bild_label.image = photo
        after_id[0] = root.after(33, einzelbild_aktualisieren)

    def foto_klick() -> None:
        frame = letzter_frame[0]
        if frame is None:
            messagebox.showinfo(
                get_string("app.schnellbild.dialog_kein_bild_titel", locale),
                get_string("app.schnellbild.dialog_kein_bild_text", locale),
                parent=root,
            )
            return
        ts = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        ziel = _speicher_ordner() / f"schnellbild_{ts}.png"
        try:
            cv2.imwrite(str(ziel), frame)
            status.configure(
                text=get_string("app.schnellbild.status_gespeichert", locale).format(
                    pfad=str(ziel)
                )
            )
        except Exception as e:
            messagebox.showerror(
                get_string("app.schnellbild.dialog_fehler_titel", locale),
                str(e),
                parent=root,
            )

    btn_zeile = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    btn_zeile.pack(anchor=tk.W, pady=(12, 0))

    b_foto = tk.Button(
        btn_zeile,
        text=get_string("app.schnellbild.btn_foto", locale),
        command=foto_klick,
        **btn_style(),
    )
    b_foto.pack(side=tk.LEFT)

    hinweis = tk.Label(
        aussen,
        text=get_string("app.schnellbild.ordner_hinweis", locale).format(
            ordner=str(_speicher_ordner())
        ),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 9),
        wraplength=560,
        justify=tk.LEFT,
    )
    hinweis.pack(anchor=tk.W, pady=(12, 0))

    def beim_zerstoeren(_e: tk.Event | None = None) -> None:
        if _e is not None and _e.widget != aussen:
            return
        preview_laeuft[0] = False
        if after_id[0] is not None:
            try:
                root.after_cancel(after_id[0])
            except tk.TclError:
                pass
        cap.release()

    aussen.bind("<Destroy>", beim_zerstoeren)

    einzelbild_aktualisieren()
