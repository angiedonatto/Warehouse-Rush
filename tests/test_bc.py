"""Clonación de comportamiento: demostraciones, pretraining y compatibilidad con parent_run_id."""
from pathlib import Path
import shutil

import numpy as np
import pytest
import yaml

from envs import ENV_VERSION, make_env
from pipelines import bc
from pipelines.baselines import HeuristicPolicy
from pipelines.train import load_config

OPEN = "configs/layout_v0.5.json"
REW = {"invalid_interaction": -0.2, "collision": -1.0, "manhattan_progress": 0.3, "height_mismatch": -0.02}


def small_demos(episodes=4, noise=(0.0, 0.25), start=bc.DEMO_SEED_START):
    return bc.collect_demos(layout_path=OPEN, orders=3, reward_overrides=REW, episodes=episodes,
                            seed_start=start, noise=list(noise), gamma=0.99, workers=2)


def test_labels_are_the_heuristic_action_and_clean_episodes_succeed():
    demos = small_demos()
    assert demos["obs"].shape[1] == 27 and demos["obs"].dtype == np.float32
    assert len(demos["obs"]) == len(demos["actions"]) == len(demos["returns"]) == len(demos["noisy"])
    assert set(np.unique(demos["actions"])) <= set(range(8))
    assert demos["expert_clean_success"] == 1.0 and demos["noisy"].any() and (~demos["noisy"]).any()
    # El primer episodio es limpio (índice 0 -> ruido 0): sus acciones se reproducen con la heurística.
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=REW)
    obs, _ = env.reset(seed=bc.DEMO_SEED_START)
    expert, done, step = HeuristicPolicy(), False, 0
    while not done:
        action = expert.action(obs, env)
        assert action == demos["actions"][step]
        np.testing.assert_array_equal(obs, demos["obs"][step])
        obs, _, terminated, truncated, _ = env.step(action)
        done, step = terminated or truncated, step + 1


def test_returns_are_discounted_to_go_and_demos_are_deterministic():
    first, second = small_demos(), small_demos()
    assert bc.demos_sha256(first) == bc.demos_sha256(second)
    # el último paso del primer episodio (limpio) cobra la misión: el retorno a ir es esa recompensa
    ends = np.flatnonzero(np.diff(first["noisy"].astype(int)) != 0)
    last = ends[0] if len(ends) else len(first["returns"]) - 1
    assert first["returns"][last] > 40


def test_demo_seeds_do_not_overlap_the_evaluation_suites():
    forbidden = set(range(10000, 10050)) | set(range(1000, 1010)) | set(range(20000, 20050))
    seeds = set(range(bc.DEMO_SEED_START, bc.DEMO_SEED_START + 1000)) | set(range(bc.VAL_SEED_START, bc.VAL_SEED_START + 100))
    assert not (seeds & forbidden)


def test_pretrained_model_loads_as_parent_and_fits_better_than_chance():
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    from pipelines.train import train_ppo

    demos, validation = small_demos(12), small_demos(4, start=bc.VAL_SEED_START)
    env = DummyVecEnv([lambda: make_env(layout_path=OPEN, orders=3, reward_overrides=REW) for _ in range(2)])
    model = PPO("MlpPolicy", env, seed=0, device="cpu", n_steps=64, batch_size=64,
                policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]}})
    before = bc.evaluate_fit(model.policy, demos)["train"]["accuracy"]
    fit = bc.pretrain(model, demos, epochs=15, lr=1e-3, batch_size=128, seed=0, validation=validation)
    assert fit["train"]["accuracy"] > max(before, 0.5)
    parent = Path("models/_test_bc_parent")
    run = "_test_bc_child"
    try:
        parent.mkdir(parents=True)
        model.save(parent / "model.zip")
        meta = train_ppo(timesteps=128, seed=0, orders=3, layout_path=OPEN, run_name=run, n_envs=2, eval_every=128,
                         eval_episodes=1, parent_model=parent / "model.zip", reward_overrides=REW,
                         ppo=dict(n_steps=64, batch_size=64, ent_coef=0.0, net_arch=[64, 64]))
        assert meta["status"] == "completed" and meta["parent_model"].endswith("model.zip")
    finally:
        for path in (parent, Path("models") / run, Path("docs/resultados/training") / run, Path("models/ppo_orders3_seed0.zip"),
                     Path("models/ppo_orders3_seed0.json")):
            shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True)


def test_h0_h1_configs_pair_by_seed_and_only_the_initialisation_differs_from_e4l():
    e4l = yaml.safe_load(Path("configs/experiments/m1o_e4l_seed0.yaml").read_text())
    for seed in (0, 1, 2):
        h0 = load_config(f"configs/experiments/m1o_h0_bc_seed{seed}.yaml")
        h1 = load_config(f"configs/experiments/m1o_h1_bcppo_seed{seed}.yaml")
        assert h0["environment_version"] == h1["environment_version"] == ENV_VERSION
        assert h0["seed"] == h1["seed"] == seed and h1["parent_run_id"] == f"m1o-h0-seed{seed}" and h0["parent_run_id"] is None
        assert h1["recompensa"] == h0["recompensa"] == e4l["recompensa"]
        assert h1["ppo"] == h0["ppo"] == e4l["ppo"] and h1["presupuesto_pasos"] == e4l["presupuesto_pasos"] == 600000
        assert h1["layout"] == h0["layout"] == e4l["layout"] and "carry_milestone" not in h1["recompensa"]
        assert h0["bc"]["noise"][0] == 0.0 and h0["presupuesto_pasos"] == 0
