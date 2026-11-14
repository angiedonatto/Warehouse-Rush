"""Parada por estancamiento (solo entrenamiento): trunca tras `window` pasos sin superar el mejor potencial."""
import pytest

from envs import make_env
from envs.env import Action
from pipelines.baselines import HeuristicPolicy
from pipelines.train import StagnationStop, load_config

WALLED = "configs/layout_v0.4.json"
R = {"invalid_interaction": -0.2, "collision": -1.0, "progress": 0.0, "potential": 30.0}


def test_idle_episode_is_truncated_not_terminated_after_the_window():
    env = StagnationStop(make_env(layout_path=WALLED, orders=3, reward_overrides=R), window=100)
    env.reset(seed=10000)
    for step in range(1, 400):
        _, _, terminated, truncated, info = env.step(int(Action.FRENAR))
        if truncated:
            break
    assert truncated and not terminated and step == 100
    assert info["end_reason"] == "stagnation" and info["stagnation_stop"] is True


def test_counter_resets_on_reset_and_on_new_best_potential():
    env = StagnationStop(make_env(layout_path=WALLED, orders=3, reward_overrides=R), window=100)
    env.reset(seed=10000)
    for _ in range(60):
        env.step(int(Action.FRENAR))
    env.reset(seed=10001)
    assert env._since == 0
    steps = 0
    truncated = False
    while not truncated:
        _, _, _, truncated, _ = env.step(int(Action.FRENAR))
        steps += 1
    assert steps == 100   # cuenta desde el reset, no desde el episodio anterior


def test_heuristic_missions_are_never_cut_and_still_succeed():
    for seed in range(10000, 10006):
        env = StagnationStop(make_env(layout_path=WALLED, orders=3, reward_overrides=R), window=100)
        obs, _ = env.reset(seed=seed)
        policy, done = HeuristicPolicy(), False
        while not done:
            obs, _, terminated, truncated, info = env.step(policy.action(obs, env.unwrapped))
            done = terminated or truncated
        assert info["success"] and "stagnation_stop" not in info


def test_window_validated_and_config_key_checked(tmp_path):
    with pytest.raises(ValueError):
        StagnationStop(make_env(layout_path=WALLED, orders=3), window=0)
    cfg = load_config("configs/experiments/m1_p1_potencial_seed0.yaml")
    assert cfg["parada_estancamiento"] == 100
    bad = tmp_path / "bad.yaml"
    bad.write_text(open("configs/experiments/m1_p1_potencial_seed0.yaml").read().replace("parada_estancamiento: 100", "parada_estancamiento: -3"))
    with pytest.raises(ValueError):
        load_config(bad)
