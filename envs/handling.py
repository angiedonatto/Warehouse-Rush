"""Dimensiones y consumos del elevador simulado; no representa hardware certificado.

v2: la bandeja ocupa posiciones discretas (0 = recogida/viaje a 0.55 m, 1..3 = baldas).
Cada acción SUBIR/BAJAR la mueve una posición; el consumo vertical sigue siendo por metro.
"""
from dataclasses import dataclass
import math

# Tres baldas de almacenamiento sobre la base estructural del rack existente.
LEVEL_HEIGHTS = (.99, 1.79, 2.60)


@dataclass(frozen=True)
class LiftConfig:
    travel_height: float = .55
    max_height: float = 2.60
    meters_per_step: float = .40     # sólo informativo (visor); en v2 el avance es por posición
    energy_per_meter: float = .80
    battery_reserve: float = 5.0

    @property
    def positions(self):
        return (self.travel_height, *LEVEL_HEIGHTS)

    def index(self, height):
        """Posición discreta (0..3) más cercana a una altura."""
        return min(range(len(self.positions)), key=lambda i: abs(self.positions[i] - height))

    def cycles(self, height):
        """Acciones SUBIR + BAJAR para ir de la posición de viaje a una balda y volver."""
        return 2 * self.index(height)

    def normalized(self, height):
        """Elevación en [0,1]: 0 en posición de viaje, 1 en la balda más alta."""
        span = self.max_height - self.travel_height
        return min(1.0, max(0.0, (height - self.travel_height) / span))
