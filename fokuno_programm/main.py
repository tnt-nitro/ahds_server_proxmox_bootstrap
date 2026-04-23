#!/usr/bin/env python3
"""Einstieg für fokuno_programm – von diesem Ordner aus starten."""

from __future__ import annotations

import sys
from pathlib import Path

_STAMM = Path(__file__).resolve().parent
if str(_STAMM) not in sys.path:
    sys.path.insert(0, str(_STAMM))

from locales import get_string
from modules.app_umgebung import app_umgebung_laden
from modules.version_info import load_version_info


def main() -> None:
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "kalender":
            from modules.kalender.demo import run_demo

            run_demo(locale="de")
            return
        if arg in ("app", "shell", "haupt"):
            from modules.app_shell import run_app

            run_app(locale="de")
            return

    info = load_version_info()
    locale = "de"
    name = get_string("app.name", locale)
    willkommen = get_string("programm.willkommen", locale)
    label = get_string("programm.version_label", locale)
    um = app_umgebung_laden()
    um_hinweis = get_string("programm.deployment_hinweis", locale).format(env=um)
    print(f"{name} - {willkommen}")
    print(f"{label}: {info.display()}")
    print(um_hinweis)


if __name__ == "__main__":
    main()
