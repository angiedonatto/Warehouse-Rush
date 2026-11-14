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
    assert asdict(reward_config()) == {"pickup": 10.0, "delivery": 30.0, "completion": 50.0, "progress": 0.3, "distance": 0.0, "manhattan_progress": 0.0, "height_mismatch": 0.0, "lower_bonus": 0.0,
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
    control = raw("m1o_c0_control")
    assert control["environment_version"] == "warehouse-v4" and control["layout"] == OPEN and control["recompensa"] == {"invalid_interaction": -0.2, "collision": -1.0, "distance": 0.0}
    seen = []
    for name in ("m1o_d1_distancia_0005", "m1o_d2_distancia_001", "m1o_d3_distancia_002"):
        cfg = raw(name)
        assert cfg["layout"] == OPEN and cfg["nivel"] == "m1o"
        assert {k: v for k, v in cfg["recompensa"].items() if k != "distance"} == {"invalid_interaction": -0.2, "collision": -1.0}
        assert cfg["recompensa"]["distance"] < 0
        seen.append(cfg["recompensa"]["distance"])
    assert seen == sorted(seen, reverse=True) and len(set(seen)) == 3


# --- v5: diferencia de distancia Manhattan y penalización por altura de bandeja distinta ---
NEW = {"manhattan_progress": 0.3, "height_mismatch": -0.1, "invalid_interaction": -0.2, "collision": -1.0}


def to_pickup_pose(env, policy, obs):
    """Lleva al robot a la celda de interacción, mirando al estante, detenido y con la bandeja abajo."""
    while not (env.state.etapa == "recoger" and env.facing_target() and env.state.v == 0 and env.tray_level() == 0):
        obs, *_ = env.step(policy.action(obs, env))
    return obs


def test_new_terms_default_off_and_signs_validated():
    env = make_env(layout_path=OPEN, orders=3)
    env.reset(seed=0)
    comp = env.step(Action.AVANZAR)[4]["reward_components"]
    assert comp["manhattan_progress"] == 0.0 and comp["height_mismatch"] == 0.0
    for bad in ({"manhattan_progress": -0.1}, {"height_mismatch": 0.1}):
        with pytest.raises(ValueError):
            reward_config(bad)


def test_manhattan_difference_rewards_approach_penalizes_retreat_and_loops_net_zero():
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    env.reset(seed=0)
    env.state.x, env.state.y, env.state.theta, env.state.v = 3, 16, 1, 0.0    # al este; celda (4,16) libre
    tx, ty = env.layout.stations[env.state.objetivo]
    before = abs(3 - tx) + abs(16 - ty)
    gains = []
    for action in (Action.AVANZAR, Action.GIRAR_DERECHA, Action.GIRAR_DERECHA, Action.AVANZAR):
        info = env.step(action)[4]
        gains.append(info["reward_components"]["manhattan_progress"])
    after = abs(env.state.x - tx) + abs(env.state.y - ty)
    assert (env.state.x, env.state.y) == (3, 16) and after == before
    assert sum(gains) == pytest.approx(0.0)                       # ida y vuelta no rinde
    assert gains[0] == pytest.approx(-gains[3]) and gains[0] != 0   # alejarse resta lo que acercarse suma


def test_manhattan_difference_has_no_jump_when_the_target_changes():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    obs, _ = env.reset(seed=10002)
    policy = HeuristicPolicy()
    done = False
    while not done:
        before = env.state.objetivo
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        done = term or trunc
        if info["reward_components"]["pickup"]:
            assert env.state.objetivo != before
            # La distancia Manhattan al objetivo NUEVO es muy distinta (el término por estado de v4 saltaba aquí)...
            assert abs(env.manhattan_to(env.state.objetivo) - env.manhattan_to(before)) >= 3
            # ...pero la diferencia usa el mismo objetivo antes y después del paso: no paga ni cobra el cambio.
            assert info["reward_components"]["manhattan_progress"] == 0.0
            return
    pytest.fail("no hubo recogida")


def test_height_mismatch_only_at_the_interaction_cell_and_scales_with_levels():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    obs, _ = env.reset(seed=10020)                     # primer producto en E05, nivel 1 o 2
    assert env.step(Action.FRENAR)[4]["reward_components"]["height_mismatch"] == 0.0   # lejos del estante
    obs = to_pickup_pose(env, HeuristicPolicy(), obs)
    needed = env.needed_tray_level()
    assert needed >= 1
    comp = env.step(Action.FRENAR)[4]["reward_components"]
    assert comp["height_mismatch"] == pytest.approx(-0.1 * needed)
    while env.tray_level() < needed:                   # SUBIR reduce la penalización hasta anularla
        env.step(Action.SUBIR)
    assert env.step(Action.FRENAR)[4]["reward_components"]["height_mismatch"] == 0.0


def test_height_mismatch_at_dispatch_requires_the_tray_down():
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    env.reset(seed=0)
    env.state.etapa, env.state.objetivo = "entregar", "DELIVERY"
    env.state.x, env.state.y, env.state.theta, env.state.v = 21, 16, 1, 0.0
    env.lift_height, env.lift_target, env.lift_phase = 0.99, 0.99, "ready"
    comp = env.step(Action.FRENAR)[4]["reward_components"]
    assert comp["height_mismatch"] == pytest.approx(-0.1)


def test_raising_and_lowering_at_the_rack_is_never_profitable():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    obs, _ = env.reset(seed=10020)
    obs = to_pickup_pose(env, HeuristicPolicy(), obs)
    total = 0.0
    for _ in range(20):
        for action in (Action.SUBIR, Action.BAJAR):
            _, reward, term, trunc, _ = env.step(action)
            total += reward
    assert total < 0


def test_v5_experiment_configs_change_only_the_new_terms():
    control = raw("m1o_c0_control")["recompensa"]
    assert control == {"invalid_interaction": -0.2, "collision": -1.0, "distance": 0.0}
    for name, expect in (("m1o_e1_manhattan_dif", (0.3, 0.0)), ("m1o_e2_altura_01", (0.0, -0.1)),
                         ("m1o_e3_ambos_01", (0.3, -0.1)), ("m1o_e4_ambos_002", (0.3, -0.02))):
        cfg = raw(name)
        assert cfg["layout"] == OPEN and cfg["nivel"] == "m1o"
        rec = cfg["recompensa"]
        assert rec["invalid_interaction"] == -0.2 and rec["collision"] == -1.0 and "distance" not in rec
        assert (rec["manhattan_progress"], rec["height_mismatch"]) == expect


def test_e4_long_seeds_control_and_e5_configs():
    e4 = raw("m1o_e4_ambos_002")
    for s in (0, 1, 2):
        cfg = raw(f"m1o_e4l_seed{s}")
        assert cfg["seed"] == s and cfg["presupuesto_pasos"] == 600000 and cfg["id"] == "e4l"
        assert cfg["recompensa"] == e4["recompensa"] and cfg["ppo"] == e4["ppo"] and cfg["layout"] == OPEN
    ctrl = raw("m1o_c0l_control_600k")
    assert ctrl["presupuesto_pasos"] == 600000 and ctrl["seed"] == 0
    assert ctrl["recompensa"] == {"invalid_interaction": -0.2, "collision": -1.0}
    e5 = raw("m1o_e5_altura_005")
    assert e5["presupuesto_pasos"] == 200000 and e5["seed"] == 0
    assert e5["recompensa"] == {**e4["recompensa"], "height_mismatch": -0.05}
    assert e5["ppo"] == e4["ppo"] and e5["layout"] == OPEN


# --- v6: bono por bajar la bandeja camino al despacho (`lower_bonus`) ---
V6 = {**NEW, "height_mismatch": -0.02, "lower_bonus": 1.0, "time": -0.2}


def play_until(env, policy, obs, stop):
    """Sigue a la heurística hasta que `stop(env)` sea cierto (o termine el episodio)."""
    while not stop(env):
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        if term or trunc:
            break
    return obs


def all_picked_with_tray_up(env):
    return len(env.picked_packages) == env.orders and env.tray_level() > 0


def test_lower_bonus_default_off_and_sign_validated():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    obs, _ = env.reset(seed=10002)
    obs = play_until(env, HeuristicPolicy(), obs, all_picked_with_tray_up)
    *_, info = env.step(Action.BAJAR)
    assert info["reward_components"]["lower_bonus"] == 0.0
    with pytest.raises(ValueError):
        reward_config({"lower_bonus": -1.0})


def test_after_the_last_pickup_the_target_is_the_delivery_point():
    from pipelines.baselines import HeuristicPolicy
    for seed in range(10000, 10010):
        env = make_env(layout_path=OPEN, orders=3, reward_overrides=V6)
        obs, _ = env.reset(seed=seed)
        obs = play_until(env, HeuristicPolicy(), obs, lambda e: len(e.picked_packages) == e.orders)
        dx, dy = env.layout.stations["DELIVERY"]
        assert env.state.objetivo == "DELIVERY" and env.state.etapa == "entregar"
        assert (obs[10] * (env.layout.width - 1), obs[11] * (env.layout.height - 1)) == pytest.approx((dx, dy), abs=1e-4)
        assert env.route_distance() > 0
        assert env.manhattan_to("DELIVERY") == abs(env.state.x - dx) + abs(env.state.y - dy)


def test_lower_bonus_pays_per_level_only_far_from_delivery_and_only_once():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=V6)
    obs, _ = env.reset(seed=10005)           # última recogida en la balda 3
    obs = play_until(env, HeuristicPolicy(), obs, all_picked_with_tray_up)
    start = env.tray_level()
    assert start >= 1 and env.route_distance() > 0
    paid = []
    for _ in range(start):
        *_, info = env.step(Action.BAJAR)
        paid.append(info["reward_components"]["lower_bonus"])
    assert paid == [1.0] * start and env.tray_level() == 0
    *_, info = env.step(Action.BAJAR)         # ya en 0: inválida, sin bono
    assert info["reward_components"]["lower_bonus"] == 0.0


def test_raising_and_lowering_on_the_way_to_delivery_is_not_farmable():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=V6)
    obs, _ = env.reset(seed=10005)
    obs = play_until(env, HeuristicPolicy(), obs, all_picked_with_tray_up)
    start = env.tray_level()
    total = 0.0
    for action in [Action.BAJAR, Action.SUBIR] * 30 + [Action.BAJAR] * (start + 1):
        *_, info = env.step(action)
        total += info["reward_components"]["lower_bonus"]
    assert total == pytest.approx(1.0 * start)       # nunca más de un bono por puesto y tramo


def test_no_bonus_while_the_target_is_a_rack_or_at_the_delivery_cell():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=V6)
    obs, _ = env.reset(seed=10002)
    obs = to_pickup_pose(env, HeuristicPolicy(), obs)
    for _ in range(3):
        env.step(Action.SUBIR)
    *_, info = env.step(Action.BAJAR)                # objetivo = estante: sin bono
    assert info["reward_components"]["lower_bonus"] == 0.0
    # en la celda de entrega (distancia 0) el bono tampoco aplica
    env2 = make_env(layout_path=OPEN, orders=3, reward_overrides=V6)
    obs, _ = env2.reset(seed=10002)
    obs = play_until(env2, HeuristicPolicy(), obs, all_picked_with_tray_up)
    obs = play_until(env2, HeuristicPolicy(), obs, lambda e: e.tray_level() == 0)
    assert env2.tray_level() == 0


def test_v6_with_new_terms_off_matches_v5_returns():
    """lower_bonus = 0 deja intacto el retorno de v5 (e4): mismo episodio guionizado, mismo retorno."""
    from pipelines.baselines import HeuristicPolicy
    returns = []
    for overrides in ({**NEW, "height_mismatch": -0.02}, {**NEW, "height_mismatch": -0.02, "lower_bonus": 0.0}):
        env = make_env(layout_path=OPEN, orders=3, reward_overrides=overrides)
        obs, _ = env.reset(seed=10003)
        policy, total, done = HeuristicPolicy(), 0.0, False
        while not done:
            obs, reward, term, trunc, info = env.step(policy.action(obs, env))
            total, done = total + reward, term or trunc
        returns.append(total)
    assert returns[0] == returns[1]


def test_v6_experiment_configs_change_only_time_and_lower_bonus():
    e4 = raw("m1o_e4l_seed0")
    expected = {"m1o_f1_tiempo_bono_seed0": (0, {"time": -0.2, "lower_bonus": 1.0}),
                "m1o_f1_tiempo_bono_seed1": (1, {"time": -0.2, "lower_bonus": 1.0}),
                "m1o_f1_tiempo_bono_seed2": (2, {"time": -0.2, "lower_bonus": 1.0}),
                "m1o_f2_tiempo_seed0": (0, {"time": -0.2}), "m1o_f3_bono_seed0": (0, {"lower_bonus": 1.0})}
    for name, (seed, extra) in expected.items():
        cfg = load_config(f"configs/experiments/{name}.yaml")
        assert cfg["environment_version"] == ENV_VERSION == "warehouse-v6"
        assert cfg["seed"] == seed and cfg["presupuesto_pasos"] == 600000 and cfg["layout"] == OPEN
        assert cfg["recompensa"] == {**e4["recompensa"], **extra}
        assert cfg["ppo"] == e4["ppo"] and cfg["evaluacion"] == e4["evaluacion"]
