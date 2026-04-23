"""Laufzeit-Umgebung fuer Deployments: dev, staging, prod.

Steuerung ueber Umgebungsvariable ``APP_ENV`` (kleinschreibung egal).
Standard ohne Variable: ``dev``.

Beispiele (Windows PowerShell)::

    $env:APP_ENV = 'staging'; python main.py app

Beispiele (cmd.exe)::

    set APP_ENV=prod && python main.py app
"""

from __future__ import annotations

import os
from typing import Final, Literal

AppUmgebung = Literal["dev", "staging", "prod"]

_ALIAS: Final[dict[str, AppUmgebung]] = {
    "dev": "dev",
    "development": "dev",
    "local": "dev",
    "staging": "staging",
    "stage": "staging",
    "test": "staging",
    "prod": "prod",
    "production": "prod",
    "live": "prod",
}


def app_umgebung_laden() -> AppUmgebung:
    """Liest APP_ENV; unbekannte Werte werden wie ``dev`` behandelt."""
    roh = (os.environ.get("APP_ENV") or "").strip().lower()
    if not roh:
        return "dev"
    return _ALIAS.get(roh, "dev")
