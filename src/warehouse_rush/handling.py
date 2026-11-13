"""Dimensiones y consumos del elevador simulado; no representa hardware certificado."""
from dataclasses import dataclass
import math

# Tres baldas de almacenamiento sobre la base estructural del rack existente.
LEVEL_HEIGHTS = (.99, 1.79, 2.60)


@dataclass(frozen=True)
class LiftConfig:
    travel_height: float = .55
    max_height: float = 2.60
    meters_per_step: float = .40
    energy_per_meter: float = .80
    battery_reserve: float = 5.0

    def cycles(self, height):
        return 2 * math.ceil(abs(height - self.travel_height) / self.meters_per_step)
