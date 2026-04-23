"""Liest die zentrale VERSION-Datei neben main.py (einzige Quelle für fokuno_programm)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_VERSION_LINE = re.compile(r"^VERSION\s*=\s*(.+)$", re.MULTILINE)
_BUMPED_LINE = re.compile(r"^BUMPED_AT\s*=\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class VersionInfo:
    version: str
    bumped_at: str

    def display(self) -> str:
        return f"v{self.version} ({self.bumped_at})"


def _stammordner() -> Path:
    return Path(__file__).resolve().parent.parent


def load_version_info() -> VersionInfo:
    datei = _stammordner() / "VERSION"
    roh = datei.read_text(encoding="utf-8")
    v = _VERSION_LINE.search(roh)
    t = _BUMPED_LINE.search(roh)
    if not v or not v.group(1).strip():
        raise ValueError("VERSION-Datei: VERSION=... fehlt oder ist leer.")
    version = v.group(1).strip()
    bumped = t.group(1).strip() if t else ""
    return VersionInfo(version=version, bumped_at=bumped)
