#!/usr/bin/env python3
"""Smoke-Checks fuer CI: keine Tk-mainloop, kein GUI-Start."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STAMM = Path(__file__).resolve().parent.parent
if str(_STAMM) not in sys.path:
    sys.path.insert(0, str(_STAMM))


def main() -> int:
    from modules.app_umgebung import app_umgebung_laden
    from modules.fenster_info import fenster_titel
    from modules.version_info import load_version_info

    os.environ["APP_ENV"] = "dev"
    assert app_umgebung_laden() == "dev", app_umgebung_laden()
    v = load_version_info()
    titel = fenster_titel(
        basis_titel="CiSmoke",
        version_info=v,
        benutzer="test",
        geoeffnet_um="2099-01-01 00:00:00",
        locale="de",
    )
    assert "CiSmoke" in titel
    assert v.version in titel

    os.environ["APP_ENV"] = "staging"
    assert app_umgebung_laden() == "staging"
    titel_st = fenster_titel(
        basis_titel="X",
        version_info=v,
        benutzer="u",
        geoeffnet_um="t",
        locale="de",
    )
    assert "Staging" in titel_st

    os.environ["APP_ENV"] = "unbekannt_xyz"
    assert app_umgebung_laden() == "dev"

    os.environ["APP_ENV"] = "prod"
    assert app_umgebung_laden() == "prod"
    titel_pr = fenster_titel(
        basis_titel="X",
        version_info=v,
        benutzer="u",
        geoeffnet_um="t",
        locale="en",
    )
    assert "Production" in titel_pr

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
