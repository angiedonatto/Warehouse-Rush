"""Warehouse Rush: cinemática discreta, sin motor físico continuo."""

__version__ = "0.7.0"          # versión de la ficha del ambiente (docs/ambiente-v0.7.md)
ENV_VERSION = "warehouse-v7"   # v7 = v6 sin lower_bonus + hito `carry_milestone` (mitad del camino al despacho con la carga, una vez por tramo, por defecto 0)

from dataclasses import asdict

from envs.env import WarehouseRushEnv
from envs.layout import Layout, PACKING_LAYOUT
from envs.missions import MakeupMissionEnv
from envs.rewards import RewardConfig


def reward_config(overrides: dict | None = None, layout_path=None) -> RewardConfig:
    """Recompensa del mapa con los coeficientes indicados cambiados. Claves desconocidas fallan."""
    base = dict(Layout.load(layout_path or PACKING_LAYOUT).data["rewards"])
    unknown = set(overrides or {}) - set(asdict(RewardConfig()))
    if unknown:
        raise ValueError(f"Coeficientes de recompensa desconocidos: {sorted(unknown)}")
    return RewardConfig(**{**base, **(overrides or {})})


def make_env(blocked: bool = False, layout_path=None, orders: int | None = None,
             reward_overrides: dict | None = None, **kwargs):
    """Ambiente v7 (misiones de maquillaje). Con `orders=N` cada episodio sortea N productos
    distintos de 1 unidad y repone el stock al reiniciar (entrenamiento/evaluación).
    `reward_overrides` cambia coeficientes de recompensa; sin él rige la recompensa del mapa (= v2)."""
    if orders is not None:
        kwargs = {"lines": orders, "max_per_line": 1, "restock": True, **kwargs}
    if reward_overrides:
        kwargs["rewards"] = reward_config(reward_overrides, layout_path)
    return MakeupMissionEnv(blocked=blocked, layout_path=layout_path, **kwargs)


__all__ = ["WarehouseRushEnv", "MakeupMissionEnv", "make_env", "reward_config", "ENV_VERSION", "__version__"]
