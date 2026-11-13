"""Warehouse Rush: cinemática discreta, sin motor físico continuo."""

__version__ = "0.2.0"          # versión de la ficha del ambiente (docs/ambiente-v0.2.md)
ENV_VERSION = "warehouse-v2"   # familia de modelos: v2 = solo modo maquillaje, Box(27), Discrete(8)

from envs.env import WarehouseRushEnv
from envs.missions import MakeupMissionEnv


def make_env(blocked: bool = False, layout_path=None, orders: int | None = None, **kwargs):
    """Ambiente v2 (misiones de maquillaje). Con `orders=N` cada episodio sortea N productos
    distintos de 1 unidad y repone el stock al reiniciar (entrenamiento/evaluación)."""
    if orders is not None:
        kwargs = {"lines": orders, "max_per_line": 1, "restock": True, **kwargs}
    return MakeupMissionEnv(blocked=blocked, layout_path=layout_path, **kwargs)


__all__ = ["WarehouseRushEnv", "MakeupMissionEnv", "make_env", "ENV_VERSION", "__version__"]
