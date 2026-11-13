"""Recompensa v3: coeficientes por run, validación y que explorar acciones inválidas nunca sea rentable."""
from dataclasses import asdict

import pytest

from envs import ENV_VERSION, make_env, reward_config
from envs.env import Action
from envs.rewards import RewardConfig
from pipelines.train import load_config

import yaml


def raw(name):
    """Configs de runs ya ejecutados en warehouse-v3: se leen como YAML, no se vuelven a entrenar."""
    with open(f"configs/experiments/{name}.yaml") as handle:
        return yaml.safe_load(handle)


def test_default_reward_equals_v2_coefficients():
    assert asdict(reward_config()) == {"pickup": 10.0, "delivery": 30.0, "completion": 50.0, "progress": 0.3, "distance": 0.0,
                                       "time": -0.1, "battery": -0.02, "collision": -5.0, "invalid_interaction": -2.0}
    assert make_env(orders=3).reward_config == reward_config()


def test_override_changes_only_the_requested_coefficient():
    env = make_env(orders=3, reward_overrides={"invalid_interaction": -0.2})
    expected = {**asdict(reward_config()), "invalid_interaction": -0.2}
    assert asdict(env.reward_config) == expected
    env.reset(seed=0)
    _, reward, _, _, info = env.step(Action.CARGAR)     # inválida: lejos de todo estante
    assert info["reward_components"]["invalid_interaction"] == pytest.approx(-0.2)
    assert reward == pytest.approx(sum(info["reward_components"].values()))


@pytest.mark.parametrize("overrides", [{"foo": 1.0}, {"invalid_interaction": 0.5}, {"time": 0.1}, {"pickup": float("nan")}])
def test_invalid_reward_overrides_are_rejected(overrides):
    with pytest.raises(ValueError):
        reward_config(overrides)


@pytest.mark.parametrize("penalty", [-2.0, -0.2, -0.05, 0.0])
def test_invalid_action_spam_is_never_profitable(penalty):
    env = make_env(orders=3, reward_overrides={"invalid_interaction": penalty})
    env.reset(seed=0)
    total = 0.0
    for _ in range(50):
        for action in (Action.CARGAR, Action.DESCARGAR, Action.SUBIR, Action.BAJAR):
            _, reward, term, trunc, _ = env.step(action)
            total += reward
            assert reward < 0
            if term or trunc:
                return
    assert total < 0


def test_config_loader_validates_reward_block(tmp_path):
    ok = tmp_path / "ok.yaml"
    ok.write_text(f"id: t\nhipotesis: x\nnivel: m1\nenvironment_version: {ENV_VERSION}\nseed: 0\n"
                  "presupuesto_pasos: 1000\nrecompensa:\n  invalid_interaction: -0.2\nppo: {}\n")
    assert load_config(ok)["recompensa"] == {"invalid_interaction": -0.2}
    bad = tmp_path / "bad.yaml"
    bad.write_text(ok.read_text().replace("invalid_interaction: -0.2", "bogus: 1"))
    with pytest.raises(ValueError):
        load_config(bad)
    old = tmp_path / "old.yaml"
    old.write_text(ok.read_text().replace(ENV_VERSION, "warehouse-v2"))
    with pytest.raises(ValueError):
        load_config(old)


def test_experiment_configs_change_one_dimension():
    for name in ("m1_r1_invalida_1", "m1_r2_invalida_02", "m1_r3_invalida_005"):
        config = raw(name)
        assert config["environment_version"] == "warehouse-v3"
        assert list(config["recompensa"]) == ["invalid_interaction"]
        assert -2.0 < config["recompensa"]["invalid_interaction"] < 0
    assert "recompensa" not in raw("m1_c0b_control_v3")


def test_collision_override_applies_and_bumping_is_never_profitable():
    for penalty in (-5.0, -2.0, -0.5, -0.1, 0.0):
        env = make_env(orders=3, reward_overrides={"invalid_interaction": -0.2, "collision": penalty})
        env.reset(seed=0)
        env.step(Action.AVANZAR)                      # BASE (3,16) -> (3,15)
        _, reward, _, _, info = env.step(Action.AVANZAR)   # (3,14) es el muro interior: choque
        assert info["collisions"] == 1
        assert info["reward_components"]["collision"] == pytest.approx(penalty)
        assert reward < 0                              # tiempo y batería siguen restando aunque el choque cueste 0


def test_collision_sweep_configs_change_one_dimension_from_r2():
    r2 = raw("m1_r2_invalida_02")["recompensa"]
    assert r2 == {"invalid_interaction": -0.2}
    seen = []
    for name in ("m1_r4_choque_2", "m1_r5_choque_1", "m1_r6_choque_05", "m1_r7_choque_01"):
        rec = raw(name)["recompensa"]
        assert rec["invalid_interaction"] == -0.2 and set(rec) == {"invalid_interaction", "collision"}
        assert -5.0 < rec["collision"] < 0
        seen.append(rec["collision"])
    assert seen == sorted(seen) and len(set(seen)) == 4


# --- Término de distancia Manhattan y mapa abierto (nivel m1o) ---
OPEN = "configs/layout_v0.5.json"


def test_distance_term_is_manhattan_to_the_previous_target_and_default_is_off():
    env = make_env(layout_path=OPEN, orders=3, reward_overrides={"distance": -0.01})
    env.reset(seed=0)
    target = env.state.objetivo
    tx, ty = env.layout.stations[target]
    _, reward, _, _, info = env.step(Action.FRENAR)
    expected = -0.01 * (abs(env.state.x - tx) + abs(env.state.y - ty))
    assert info["reward_components"]["distance"] == pytest.approx(expected)
    assert reward == pytest.approx(sum(info["reward_components"].values()))
    plain = make_env(layout_path=OPEN, orders=3)
    plain.reset(seed=0)
    assert plain.step(Action.FRENAR)[4]["reward_components"]["distance"] == 0.0


def test_farther_from_destination_costs_more_per_step():
    env = make_env(layout_path=OPEN, orders=3, reward_overrides={"distance": -0.02})
    env.reset(seed=0)
    free = [(x, y) for x in range(env.layout.width) for y in range(env.layout.height) if env._free((x, y))]
    dist = {cell: abs(cell[0] - env.layout.stations[env.state.objetivo][0]) + abs(cell[1] - env.layout.stations[env.state.objetivo][1])
            for cell in free}
    nearest, farthest = min(free, key=dist.get), max(free, key=dist.get)
    penalties = {}
    for name, cell in (("near", nearest), ("far", farthest)):
        env.state.x, env.state.y = cell
        env.state.v = 0.0
        penalties[name] = env.step(Action.FRENAR)[4]["reward_components"]["distance"]
    assert dist[farthest] > dist[nearest] >= 1
    assert penalties["far"] < penalties["near"] < 0
    assert penalties["far"] == pytest.approx(-0.02 * dist[farthest])


def test_positive_distance_coefficient_is_rejected():
    with pytest.raises(ValueError):
        reward_config({"distance": 0.01})


def test_open_layout_has_no_interior_wall_or_gap_and_heuristic_completes_orders():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3)
    assert env.layout.data["internal_walls"] == [] and env.layout.data["blockable_cells"] == []
    env.layout.validate_routes()
    assert len(env.layout.racks) == 24
    policy = HeuristicPolicy()
    for seed in range(5):
        obs, _ = env.reset(seed=seed)
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(policy.action(obs, env))
            done = term or trunc
        assert info["success"] and info["collisions"] == 0 and info["invalid_interactions"] == 0


def test_distance_sweep_configs_change_one_dimension_from_control():
    control = load_config("configs/experiments/m1o_c0_control.yaml")
    assert control["layout"] == OPEN and control["recompensa"] == {"invalid_interaction": -0.2, "collision": -1.0, "distance": 0.0}
    seen = []
    for name in ("m1o_d1_distancia_0005", "m1o_d2_distancia_001", "m1o_d3_distancia_002"):
        cfg = load_config(f"configs/experiments/{name}.yaml")
        assert cfg["layout"] == OPEN and cfg["nivel"] == "m1o"
        assert {k: v for k, v in cfg["recompensa"].items() if k != "distance"} == {"invalid_interaction": -0.2, "collision": -1.0}
        assert cfg["recompensa"]["distance"] < 0
        seen.append(cfg["recompensa"]["distance"])
    assert seen == sorted(seen, reverse=True) and len(set(seen)) == 3
