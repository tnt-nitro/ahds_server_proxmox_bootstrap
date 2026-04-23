"""Sprachmemo: Mikrofonaufnahmen speichern und abspielen."""

from __future__ import annotations

import datetime as dt
import threading
import wave
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox

from locales import get_string
from modules.theming.farben import kalender_farben

try:
    import numpy as np
    import sounddevice as sd

    _AUDIO_OK = True
except ImportError:
    _AUDIO_OK = False

SAMPLERATE = 44100
CHANNELS = 1


def _speicher_ordner() -> Path:
    p = Path.home() / "AhDs" / "Sprachmemos"
    p.mkdir(parents=True, exist_ok=True)
    return p


class _Recorder:
    """Aufnahme über einen Hintergrund-Thread mit InputStream."""

    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._stream: object | None = None
        self._chunks: list = []

    def _run(self) -> None:
        self._chunks = []
        try:
            stream = sd.InputStream(
                samplerate=SAMPLERATE,
                channels=CHANNELS,
                dtype="float32",
            )
            self._stream = stream
            with stream:
                while not self._stop.is_set():
                    data, _overflowed = stream.read(2048)
                    self._chunks.append(data.copy())
        except Exception:
            pass
        finally:
            self._stream = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        st = self._stream
        if st is not None:
            try:
                st.abort()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=4.0)
            self._thread = None

    def get_audio(self):
        if not _AUDIO_OK or not self._chunks:
            return None
        return np.concatenate(self._chunks, axis=0)


def sprachmemo_in(parent: tk.Misc, locale: str = "de") -> None:
    """Baut die Sprachmemo-Ansicht in den übergebenen Container."""

    kf = kalender_farben()
    root = parent.winfo_toplevel()

    aussen = tk.Frame(parent, bg=kf.HINTERGRUND_FENSTER)
    aussen.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

    titel = tk.Label(
        aussen,
        text=get_string("app.sprachmemo.titel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 14, "bold"),
    )
    titel.pack(anchor=tk.W)

    if not _AUDIO_OK:
        tk.Label(
            aussen,
            text=get_string("app.sprachmemo.fehlende_abhaengigkeit", locale),
            bg=kf.HINTERGRUND_FENSTER,
            fg=kf.TEXT_ZEIT,
            font=("Segoe UI", 11),
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))
        return

    unter = tk.Label(
        aussen,
        text=get_string("app.sprachmemo.untertitel", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
        wraplength=560,
        justify=tk.LEFT,
    )
    unter.pack(anchor=tk.W, pady=(4, 12))

    status = tk.Label(
        aussen,
        text=get_string("app.sprachmemo.status_bereit", locale),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 10),
    )
    status.pack(anchor=tk.W, pady=(0, 8))

    recorder = _Recorder()
    letzte_aufnahme: list = [None]

    btn_zeile = tk.Frame(aussen, bg=kf.HINTERGRUND_FENSTER)
    btn_zeile.pack(anchor=tk.W)

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

    def start_klick() -> None:
        status.configure(text=get_string("app.sprachmemo.status_aufnahme", locale))
        b_start.configure(state=tk.DISABLED)
        b_stop.configure(state=tk.NORMAL)
        recorder.start()

    def stop_klick() -> None:
        recorder.stop()
        audio = recorder.get_audio()
        letzte_aufnahme[0] = audio
        b_start.configure(state=tk.NORMAL)
        b_stop.configure(state=tk.DISABLED)
        if audio is not None and len(audio) > 0:
            status.configure(text=get_string("app.sprachmemo.status_gespeichert_ram", locale))
        else:
            status.configure(text=get_string("app.sprachmemo.status_leer", locale))

    def abspielen_klick() -> None:
        audio = letzte_aufnahme[0]
        if audio is None or len(audio) == 0:
            messagebox.showinfo(
                get_string("app.sprachmemo.dialog_kein_audio_titel", locale),
                get_string("app.sprachmemo.dialog_kein_audio_text", locale),
                parent=root,
            )
            return
        try:
            sd.play(audio, SAMPLERATE)
        except Exception as e:
            messagebox.showerror(
                get_string("app.sprachmemo.dialog_fehler_titel", locale),
                str(e),
                parent=root,
            )

    def speichern_klick() -> None:
        audio = letzte_aufnahme[0]
        if audio is None or len(audio) == 0:
            messagebox.showinfo(
                get_string("app.sprachmemo.dialog_kein_audio_titel", locale),
                get_string("app.sprachmemo.dialog_kein_audio_text", locale),
                parent=root,
            )
            return
        ts = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        vorschlag = _speicher_ordner() / f"sprachmemo_{ts}.wav"
        pfad = filedialog.asksaveasfilename(
            parent=root,
            defaultextension=".wav",
            filetypes=[
                (get_string("app.sprachmemo.filter_wav", locale), "*.wav"),
            ],
            initialfile=vorschlag.name,
            initialdir=str(vorschlag.parent),
        )
        if not pfad:
            return
        try:
            audio_i16 = (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16)
            with wave.open(pfad, "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLERATE)
                wf.writeframes(audio_i16.tobytes())
            status.configure(
                text=get_string("app.sprachmemo.status_gespeichert_datei", locale).format(
                    pfad=pfad
                )
            )
        except OSError as e:
            messagebox.showerror(
                get_string("app.sprachmemo.dialog_fehler_titel", locale),
                str(e),
                parent=root,
            )

    b_start = tk.Button(
        btn_zeile,
        text=get_string("app.sprachmemo.btn_start", locale),
        command=start_klick,
        **btn_style(),
    )
    b_start.pack(side=tk.LEFT, padx=(0, 8))

    b_stop = tk.Button(
        btn_zeile,
        text=get_string("app.sprachmemo.btn_stop", locale),
        command=stop_klick,
        state=tk.DISABLED,
        **btn_style(),
    )
    b_stop.pack(side=tk.LEFT, padx=(0, 8))

    b_play = tk.Button(
        btn_zeile,
        text=get_string("app.sprachmemo.btn_abspielen", locale),
        command=abspielen_klick,
        **btn_style(),
    )
    b_play.pack(side=tk.LEFT, padx=(0, 8))

    b_save = tk.Button(
        btn_zeile,
        text=get_string("app.sprachmemo.btn_speichern", locale),
        command=speichern_klick,
        **btn_style(),
    )
    b_save.pack(side=tk.LEFT)

    hinweis = tk.Label(
        aussen,
        text=get_string("app.sprachmemo.ordner_hinweis", locale).format(
            ordner=str(_speicher_ordner())
        ),
        bg=kf.HINTERGRUND_FENSTER,
        fg=kf.TEXT_ZEIT,
        font=("Segoe UI", 9),
        wraplength=560,
        justify=tk.LEFT,
    )
    hinweis.pack(anchor=tk.W, pady=(16, 0))
