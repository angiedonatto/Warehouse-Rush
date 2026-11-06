"""Warehouse Rush: cinemática discreta, sin motor físico continuo."""

__version__ = "0.1.0"          # versión de la ficha del ambiente (docs/ambiente-v0.1.md)
ENV_VERSION = "warehouse-v1"   # identificador de familia de modelos (plan: warehouse-v1, v2...)

from envs.env import WarehouseRushEnv

__all__ = ["WarehouseRushEnv", "ENV_VERSION", "__version__"]
