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
    def action(self, observation, env: WarehouseRushEnv) -> int:
        if env.facing_target():
            return int(Action.FRENAR if env.state.v else Action.INTERACTUAR)
        target = env.layout.stations[env.state.objetivo]
        start = (*env.position, env.state.theta)
        queue = deque([(start, None)])
        seen = {start}
        while queue:
            (x, y, theta), first = queue.popleft()
            dx, dy = DIRECTIONS[theta]
            if (x + dx, y + dy) == target:
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
