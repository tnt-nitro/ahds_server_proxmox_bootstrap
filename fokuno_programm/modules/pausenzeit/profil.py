"""Pausen während der Regelarbeitszeit. Ausbau später: mehrere Pausen, Berufs-/Tarifmodelle."""

from __future__ import annotations

from dataclasses import dataclass

from modules.theming.farben import kalender_farben


@dataclass(frozen=True)
class Pausenblock:
    """Eine Pause [start, ende) in Minuten seit Mitternacht (ende exklusiv, wie Regelarbeit)."""

    start_stunde: int
    start_minute: int
    ende_stunde: int
    ende_minute: int

    @property
    def start_minuten_seit_mitternacht(self) -> int:
        return self.start_stunde * 60 + self.start_minute

    @property
    def ende_minuten_seit_mitternacht(self) -> int:
        return self.ende_stunde * 60 + self.ende_minute

    @property
    def dauer_minuten(self) -> int:
        return self.ende_minuten_seit_mitternacht - self.start_minuten_seit_mitternacht

    @classmethod
    def aus_start_und_dauer(
        cls, start_stunde: int, start_minute: int, dauer_minuten: int
    ) -> "Pausenblock":
        """Erzeugt einen Block aus Startzeit + Dauer (Minuten)."""
        if dauer_minuten <= 0:
            raise ValueError("dauer_minuten")
        start = start_stunde * 60 + start_minute
        ende = start + dauer_minuten
        if start < 0 or ende > 24 * 60:
            raise ValueError("zeitfenster")
        ende_stunde, ende_minute = divmod(ende, 60)
        if ende_stunde == 24 and ende_minute == 0:
            ende_stunde = 23
            ende_minute = 59
        return cls(start_stunde, start_minute, ende_stunde, ende_minute)


@dataclass(frozen=True)
class PausenProfil:
    """Eine oder mehrere Pausen pro Arbeitstag (Reihenfolge der Tupel = Reihenfolge der Blöcke)."""

    bloecke: tuple[Pausenblock, ...]
    #: Optional: tagesgenaue Pausenblöcke je Wochentag (0=Mo ... 6=So).
    tages_bloecke: dict[int, tuple[Pausenblock, ...]] | None = None
    farbe_pause_hex: str | None = None

    def pauseflaechen_farbe_hex(self) -> str:
        return self.farbe_pause_hex or kalender_farben().PAUSE_ARBEIT_FLACHE

    def bloecke_fuer_wochentag(self, wochentag: int) -> tuple[Pausenblock, ...]:
        if self.tages_bloecke is not None and wochentag in self.tages_bloecke:
            return self.tages_bloecke[wochentag]
        return self.bloecke


def standard_arbeitspausen() -> PausenProfil:
    """Voreinstellung: Frühstück, Mittag und kurze Nachmittagspause."""
    return PausenProfil(
        bloecke=(
            Pausenblock(11, 30, 11, 45),
            Pausenblock(14, 0, 14, 45),
            Pausenblock(17, 0, 17, 15),
        ),
    )
