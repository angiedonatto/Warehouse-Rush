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
    assert asdict(reward_config()) == {"pickup": 10.0, "delivery": 30.0, "completion": 50.0, "progress": 0.3, "distance": 0.0, "manhattan_progress": 0.0, "height_mismatch": 0.0, "carry_milestone": 0.0, "face_bonus": 0.0, "potential": 0.0,
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


# --- v7: hito de la mitad del camino al despacho con la carga (`carry_milestone`); v6 (lower_bonus) se retira ---
V7 = {**NEW, "height_mismatch": -0.02, "carry_milestone": 5.0}


def play_until(env, policy, obs, stop):
    """Sigue a la heurística hasta que `stop(env)` sea cierto (o termine el episodio)."""
    while not stop(env):
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        if term or trunc:
            break
    return obs


def all_picked(env):
    return len(env.picked_packages) == env.orders


def test_carry_milestone_default_off_sign_validated_and_lower_bonus_is_gone():
    from pipelines.baselines import HeuristicPolicy
    assert "lower_bonus" not in asdict(reward_config())
    with pytest.raises(ValueError):
        reward_config({"lower_bonus": 1.0})
    with pytest.raises(ValueError):
        reward_config({"carry_milestone": -1.0})
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=NEW)
    obs, _ = env.reset(seed=10002)
    policy, paid, done = HeuristicPolicy(), 0.0, False
    while not done:
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        paid += info["reward_components"]["carry_milestone"]
        done = term or trunc
    assert paid == 0.0


def test_after_the_last_pickup_the_target_is_the_delivery_point():
    from pipelines.baselines import HeuristicPolicy
    for seed in range(10000, 10010):
        env = make_env(layout_path=OPEN, orders=3, reward_overrides=V7)
        obs, _ = env.reset(seed=seed)
        obs = play_until(env, HeuristicPolicy(), obs, all_picked)
        dx, dy = env.layout.stations["DELIVERY"]
        assert env.state.objetivo == "DELIVERY" and env.state.etapa == "entregar"
        assert (obs[10] * (env.layout.width - 1), obs[11] * (env.layout.height - 1)) == pytest.approx((dx, dy), abs=1e-4)
        assert env.route_distance() > 0
        assert env.manhattan_to("DELIVERY") == abs(env.state.x - dx) + abs(env.state.y - dy)


def test_carry_milestone_pays_once_at_half_the_distance_and_never_before():
    from pipelines.baselines import HeuristicPolicy
    for seed in (10000, 10004, 10005):
        env = make_env(layout_path=OPEN, orders=3, reward_overrides=V7)
        obs, _ = env.reset(seed=seed)
        policy = HeuristicPolicy()
        obs = play_until(env, policy, obs, all_picked)
        start = env.route_distance()
        events, done = [], False
        while not done:
            obs, _, term, trunc, info = env.step(policy.action(obs, env))
            done = term or trunc
            paid = info["reward_components"]["carry_milestone"]
            if paid:
                events.append((start, env.route_distance()))
        assert len(events) == 1
        assert events[0][1] * 2 <= events[0][0]


def test_carry_milestone_is_not_farmable_by_oscillating():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=V7)
    obs, _ = env.reset(seed=10000)
    policy = HeuristicPolicy()
    obs = play_until(env, policy, obs, all_picked)
    obs = play_until(env, policy, obs, lambda e: e.tray_level() == 0)       # baja la bandeja; aún lejos del despacho
    total = 0.0
    for _ in range(40):                                                     # avanza y retrocede 80 pasos
        for action in (Action.AVANZAR, Action.GIRAR_DERECHA, Action.GIRAR_DERECHA, Action.AVANZAR,
                       Action.GIRAR_DERECHA, Action.GIRAR_DERECHA):
            *_, info = env.step(action)
            total += info["reward_components"]["carry_milestone"]
    assert total <= 5.0


def test_no_milestone_while_the_target_is_a_rack():
    from pipelines.baselines import HeuristicPolicy
    env = make_env(layout_path=OPEN, orders=3, reward_overrides=V7)
    obs, _ = env.reset(seed=10002)
    policy, total, done = HeuristicPolicy(), 0.0, False
    while not done and not env.picked_packages:
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        total += info["reward_components"]["carry_milestone"]
        done = term or trunc
    assert total == 0.0


def test_v7_with_milestone_off_matches_v5_returns():
    """carry_milestone = 0 deja intacto el retorno de v5 (e4): mismo episodio guionizado, mismo retorno."""
    from pipelines.baselines import HeuristicPolicy
    returns = []
    for overrides in ({**NEW, "height_mismatch": -0.02}, {**NEW, "height_mismatch": -0.02, "carry_milestone": 0.0}):
        env = make_env(layout_path=OPEN, orders=3, reward_overrides=overrides)
        obs, _ = env.reset(seed=10003)
        policy, total, done = HeuristicPolicy(), 0.0, False
        while not done:
            obs, reward, term, trunc, info = env.step(policy.action(obs, env))
            total, done = total + reward, term or trunc
        returns.append(total)
    assert returns[0] == returns[1]


def test_v6_configs_are_history_and_v7_configs_change_only_the_milestone():
    for name in ("m1o_f1_tiempo_bono_seed0", "m1o_f2_tiempo_seed0", "m1o_f3_bono_seed0"):
        assert raw(name)["environment_version"] == "warehouse-v6"
    e4 = raw("m1o_e4l_seed0")
    for seed in (0, 1, 2):
        cfg = raw(f"m1o_g1_hito_seed{seed}")
        assert cfg["environment_version"] == "warehouse-v7"   # historia: v8 solo añade face_bonus (por defecto 0)
        assert cfg["seed"] == seed and cfg["presupuesto_pasos"] == 600000 and cfg["layout"] == OPEN
        assert cfg["recompensa"] == {**e4["recompensa"], "carry_milestone": 5.0}
        assert "time" not in cfg["recompensa"] and "lower_bonus" not in cfg["recompensa"]
        assert cfg["ppo"] == e4["ppo"] and cfg["evaluacion"] == e4["evaluacion"]


def test_more_seeds_configs_replicate_e4l_and_g1_with_only_the_seed_changed():
    for seed in range(3, 8):
        e4l = raw(f"m1o_e4l_seed{seed}")
        g1 = raw(f"m1o_g1_hito_seed{seed}")
        base = raw("m1o_g1_hito_seed0")
        assert e4l["seed"] == g1["seed"] == seed
        assert e4l["environment_version"] == g1["environment_version"] == "warehouse-v7"
        assert e4l["recompensa"] == {k: v for k, v in g1["recompensa"].items() if k != "carry_milestone"}
        assert g1["recompensa"] == base["recompensa"] and g1["ppo"] == base["ppo"] == e4l["ppo"]
        assert e4l["presupuesto_pasos"] == g1["presupuesto_pasos"] == 600000 and e4l["layout"] == g1["layout"]


# --- v8: face_bonus (una vez por estación objetivo y episodio al estar en su celda de interacción mirándola) ---
WALLED = "configs/layout_v0.4.json"
V8 = {**NEW, "height_mismatch": -0.02, "face_bonus": 5.0}


def test_face_bonus_default_off_sign_validated_and_version():
    assert ENV_VERSION == "warehouse-v9"   # v9 solo añade `potential`; v8 sigue igual con potential = 0
    assert asdict(reward_config())["face_bonus"] == 0.0
    with pytest.raises(ValueError):
        reward_config({"face_bonus": -1.0})


def run_heuristic(env, seed):
    from pipelines.baselines import HeuristicPolicy
    obs, _ = env.reset(seed=seed)
    policy, rows, done = HeuristicPolicy(), [], False
    while not done:
        obs, reward, term, trunc, info = env.step(policy.action(obs, env))
        rows.append((reward, info["reward_components"].copy()))
        done = term or trunc
    return rows, info


def test_face_bonus_zero_keeps_v7_returns_and_pays_each_station_once():
    for layout in (OPEN, WALLED):
        base = make_env(layout_path=layout, orders=3, reward_overrides={**V8, "face_bonus": 0.0})
        on = make_env(layout_path=layout, orders=3, reward_overrides=V8)
        rows0, info0 = run_heuristic(base, 10003)
        rows1, info1 = run_heuristic(on, 10003)
        paid = [c["face_bonus"] for _, c in rows1 if c["face_bonus"]]
        assert all(c["face_bonus"] == 0.0 for _, c in rows0)
        assert set(paid) == {5.0} and 1 <= len(paid) <= len(on.layout.stations)
        assert info1["total_reward"] == pytest.approx(info0["total_reward"] + 5.0 * len(paid))
        assert info0["success"] and info1["success"]


def test_face_bonus_is_not_farmable_by_standing_or_turning_away_and_back():
    from pipelines.baselines import HeuristicPolicy
    from envs.env import Action
    env = make_env(layout_path=WALLED, orders=3, reward_overrides=V8)
    obs, _ = env.reset(seed=10003)
    policy, first, target = HeuristicPolicy(), None, None
    while first is None:
        target = env.state.objetivo
        obs, _, term, trunc, info = env.step(policy.action(obs, env))
        assert not (term or trunc)
        if info["reward_components"]["face_bonus"]:
            first = target
    extra = 0.0
    for action in [Action.FRENAR] * 10 + [Action.GIRAR_IZQUIERDA, Action.GIRAR_DERECHA] * 10:
        _, _, term, trunc, info = env.step(int(action))
        extra += info["reward_components"]["face_bonus"]
    assert first is not None and extra == 0.0
    assert first in env._face_paid


# --- v9: shaping basado en potencial (`potential`), un solo peso W; Phi(s) en [0,1] y función solo del estado ---
from envs.rewards import POTENTIAL_GAMMA
P9 = {"invalid_interaction": -0.2, "collision": -1.0, "progress": 0.0, "potential": 30.0}


def test_potential_default_off_sign_validated_and_gamma_matches_ppo():
    assert asdict(reward_config())["potential"] == 0.0
    with pytest.raises(ValueError):
        reward_config({"potential": -1.0})
    assert POTENTIAL_GAMMA == 0.99 == raw("m1_e4l_seed0")["ppo"]["gamma"]


def test_potential_is_state_only_bounded_and_ends_at_one_on_success():
    for layout in (OPEN, WALLED):
        env = make_env(layout_path=layout, orders=3, reward_overrides=P9)
        rows, info = run_heuristic(env, 10003)
        assert info["success"] and env.potential() == pytest.approx(1.0)
        env.reset(seed=10003)
        assert 0.0 <= env.potential() < 0.1


def test_potential_discounted_sum_telescopes_exactly():
    for layout in (OPEN, WALLED):
        env = make_env(layout_path=layout, orders=3, reward_overrides=P9)
        from pipelines.baselines import HeuristicPolicy
        obs, _ = env.reset(seed=10004)
        policy, done, t, discounted = HeuristicPolicy(), False, 0, 0.0
        p0 = env.potential()
        while not done:
            obs, _, term, trunc, info = env.step(policy.action(obs, env))
            discounted += POTENTIAL_GAMMA ** t * info["reward_components"]["potential"]
            done, t = term or trunc, t + 1
        assert discounted == pytest.approx(30.0 * (POTENTIAL_GAMMA ** t * env.potential() - p0))


def test_potential_zero_weight_keeps_v8_returns():
    a = make_env(layout_path=WALLED, orders=3, reward_overrides={**P9, "potential": 0.0})
    b = make_env(layout_path=WALLED, orders=3, reward_overrides={k: v for k, v in P9.items() if k != "potential"})
    ra, ia = run_heuristic(a, 10005)
    rb, ib = run_heuristic(b, 10005)
    assert ia["total_reward"] == pytest.approx(ib["total_reward"])
    assert all(c["potential"] == 0.0 for _, c in ra)


def test_potential_cannot_be_farmed_by_standing_or_turning_away_and_back():
    from pipelines.baselines import HeuristicPolicy
    from envs.env import Action
    env = make_env(layout_path=WALLED, orders=3, reward_overrides=P9)
    obs, _ = env.reset(seed=10003)
    policy = HeuristicPolicy()
    while not (env.route_distance() == 0 and env.facing_target()):
        obs, *_ = env.step(policy.action(obs, env))
    idle = sum(env.step(int(Action.FRENAR))[4]["reward_components"]["potential"] for _ in range(30))
    assert idle < 0.0
    cycle = 0.0
    for _ in range(10):
        for action in (Action.GIRAR_IZQUIERDA, Action.GIRAR_DERECHA):
            cycle += env.step(int(action))[4]["reward_components"]["potential"]
    assert cycle < 0.0


def test_q1_configs_are_p1_with_task_rewards_and_potential_scaled_by_five():
    p1 = raw("m1_p1_potencial_seed0")
    for seed in (0, 1, 2):
        q1 = raw(f"m1_q1_escala5_seed{seed}")
        assert q1["id"] == "q1" and q1["seed"] == seed and q1["environment_version"] == "warehouse-v9"
        expected = {**p1["recompensa"], "pickup": 50.0, "delivery": 150.0, "completion": 250.0, "potential": 150.0}
        assert q1["recompensa"] == expected
        assert q1["ppo"] == p1["ppo"] and q1["layout"] == p1["layout"] == WALLED
        assert q1["presupuesto_pasos"] == p1["presupuesto_pasos"] == 600000 and q1["parada_estancamiento"] == 100
        assert q1["recompensa"]["collision"] == p1["recompensa"]["collision"] == -1.0   # penalizaciones sin escalar
