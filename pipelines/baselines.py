"""Random y heurística privilegiada; PPO sólo recibe el vector observado."""

from collections import deque
from pathlib import Path

import numpy as np

from envs.env import Action, WarehouseRushEnv
from envs.layout import DIRECTIONS


class RandomPolicy:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def action(self, observation, env: WarehouseRushEnv) -> int:
        return int(self.rng.integers(env.action_space.n))


class HeuristicPolicy:
    """Referencia privilegiada: BFS por pose y secuencia explícita de SUBIR/CARGAR/BAJAR/DESCARGAR."""

    def action(self, observation, env: WarehouseRushEnv) -> int:
        state = env.state
        if state.etapa == "completada":
            return int(Action.FRENAR)
        lift = getattr(env, "lift_config", None)
        index = lift.index(env.lift_height) if lift else 0
        if index > 0:  # bandeja arriba: no hay movimiento posible
            if state.etapa == "recoger" and env.facing_target():
                goal = lift.index(env.lines[state.pedido_actual]["height_m"])
                return int(Action.SUBIR if index < goal else Action.CARGAR if index == goal else Action.BAJAR)
            return int(Action.BAJAR)
        if env.facing_target():
            if state.v:
                return int(Action.FRENAR)
            if state.etapa == "recoger":
                return int(Action.SUBIR if lift else Action.CARGAR)
            return int(Action.DESCARGAR)
        target = env.layout.stations[env.state.objetivo]
        approaches = env.layout.approaches(env.state.objetivo, env.state.pasillo_bloqueado)
        start = (*env.position, env.state.theta)
        queue = deque([(start, None)])
        seen = {start}
        while queue:
            (x, y, theta), first = queue.popleft()
            dx, dy = DIRECTIONS[theta]
            if (x + dx, y + dy) == target and (x, y) in approaches:
                return int(first)
            successors = [((x, y, (theta - 1) % 4), Action.GIRAR_IZQUIERDA),
                          ((x, y, (theta + 1) % 4), Action.GIRAR_DERECHA)]
            if env._free((x + dx, y + dy)):
                successors.insert(0, ((x + dx, y + dy, theta), Action.AVANZAR))
            for pose, action in successors:
                if pose not in seen:
                    seen.add(pose)
                    queue.append((pose, first if first is not None else action))
        raise RuntimeError("No hay ruta heurística al objetivo")


class PPOPolicy:
    def __init__(self, model_path):
        from stable_baselines3 import PPO

        self.model = PPO.load(model_path, device="cpu")

    def action(self, observation, env: WarehouseRushEnv) -> int:
        action, _ = self.model.predict(observation, deterministic=True)
        return int(action)


class DQNPolicy:
    def __init__(self, model_path):
        from stable_baselines3 import DQN

        self.model = DQN.load(model_path, device="cpu")

    def action(self, observation, env: WarehouseRushEnv) -> int:
        action, _ = self.model.predict(observation, deterministic=True)
        return int(action)


def make_policy(name: str, seed: int = 0, model_path=None):
    if name == "random":
        return RandomPolicy(seed)
    if name == "heuristic":
        return HeuristicPolicy()
    if name == "ppo":
        if model_path is None or not Path(model_path).is_file():
            raise FileNotFoundError("Modelo PPO ausente; ejecuta train o indica --model")
        return PPOPolicy(model_path)
    if name == "dqn":
        if model_path is None or not Path(model_path).is_file():
            raise FileNotFoundError("Modelo DQN ausente; ejecuta train o indica --model")
        return DQNPolicy(model_path)
    raise ValueError(f"Política desconocida: {name}")
