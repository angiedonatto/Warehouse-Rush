"""Componentes auditables; distancia evaluada contra el objetivo ANTERIOR."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RewardConfig:
    pickup: float = 10.0
    delivery: float = 30.0
    completion: float = 50.0
    progress: float = 0.3
    time: float = -0.1
    battery: float = -0.02
    collision: float = -5.0
    invalid_interaction: float = -2.0
    distance: float = 0.0   # v4: por celda de distancia Manhattan al objetivo, por paso (<= 0; 0 = sin término)
    manhattan_progress: float = 0.0   # v5: por celda de DIFERENCIA de distancia Manhattan (>= 0): acercarse suma, alejarse resta
    height_mismatch: float = 0.0      # v5: por paso y por puesto de bandeja de diferencia con la altura exigida, solo en una celda de interacción del objetivo (<= 0)

    def __post_init__(self):
        if not all(math.isfinite(value) for value in self.__dict__.values()):
            raise ValueError("Las recompensas deben ser finitas")
        if min(self.pickup, self.delivery, self.completion, self.progress, self.manhattan_progress) < 0:
            raise ValueError("Los premios/progreso deben ser no negativos")
        if self.time >= 0 or max(self.battery, self.collision, self.invalid_interaction, self.distance, self.height_mismatch) > 0:
            raise ValueError("Tiempo negativo y penalizaciones no positivas previenen ciclos rentables")


def reward_components(config: RewardConfig, *, distance_delta: float, battery_used: float,
                      pickup: bool, delivery: bool, completion: bool,
                      collision: bool, invalid: bool, target_distance: float = 0.0,
                      manhattan_delta: float = 0.0, height_gap: float = 0.0) -> dict[str, float]:
    return {
        "pickup": config.pickup if pickup else 0.0,
        "delivery": config.delivery if delivery else 0.0,
        "completion": config.completion if completion else 0.0,
        "progress": config.progress * distance_delta,
        "time": config.time,
        "battery": config.battery * battery_used,
        "collision": config.collision if collision else 0.0,
        "invalid_interaction": config.invalid_interaction if invalid else 0.0,
        "distance": config.distance * target_distance,
        "manhattan_progress": config.manhattan_progress * manhattan_delta,
        "height_mismatch": config.height_mismatch * height_gap,
    }
