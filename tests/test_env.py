from dataclasses import replace

import numpy as np
import pytest
from stable_baselines3.common.env_checker import check_env

from envs.env import Action, SimulationConfig, WarehouseRushEnv
from envs.layout import DIRECTIONS, Layout
from pipelines.baselines import HeuristicPolicy
from envs.rewards import RewardConfig


@pytest.fixture
def env():
    environment = WarehouseRushEnv(orders=2)
    environment.reset(seed=123)
    yield environment
    environment.close()


def put_in_front(env, station):
    x, y = env.layout.stations[station]
    for theta, (dx, dy) in enumerate(DIRECTIONS):
        cell = x - dx, y - dy
        if env._free(cell):
            env.state.x, env.state.y = cell
            env.state.theta = theta
            env.state.v = 0.0
            return
    raise AssertionError("Estación sin celda de interacción")


def pickup(env):
    put_in_front(env, "P1")
    return env.step(Action.CARGAR)


@pytest.mark.parametrize("orders,blocked", [(1, False), (1, True), (2, False), (2, True)])
def test_sb3_environment_contract(orders, blocked):
    environment = WarehouseRushEnv(orders, blocked)
    check_env(environment, warn=True)


@pytest.mark.parametrize("blocked", [False, True])
def test_observations_are_float32_finite_and_bounded(blocked):
    environment = WarehouseRushEnv(2, blocked)
    obs, _ = environment.reset(seed=71)
    rng = np.random.default_rng(71)
    for _ in range(600):
        assert obs.shape == (27,)
        assert obs.dtype == np.float32
        assert np.isfinite(obs).all()
        assert environment.observation_space.contains(obs)
        obs, _, terminated, truncated, _ = environment.step(int(rng.integers(5)))
        if terminated or truncated:
            obs, _ = environment.reset()


@pytest.mark.parametrize("action", list(Action))
def test_all_valid_actions_execute(env, action):
    obs, reward, terminated, truncated, info = env.step(action)
    assert env.observation_space.contains(obs)
    assert isinstance(reward, float)
    assert info["steps"] == 1
    assert not terminated and not truncated


@pytest.mark.parametrize("bad_action", [-1, 8, 1.5, "forward"])
def test_out_of_space_actions_rejected_without_state_change(env, bad_action):
    before = env.snapshot()
    with pytest.raises(ValueError):
        env.step(bad_action)
    assert env.snapshot() == before


@pytest.mark.parametrize("position,theta", [((1, 1), 3), ((2, 3), 1), ((2, 11), 0), ((2, 2), 0)])
def test_walls_racks_internal_wall_and_station_cannot_be_crossed(env, position, theta):
    env.state.x, env.state.y = position
    env.state.theta = theta
    _, reward, _, _, info = env.step(Action.AVANZAR)
    assert env.position == position
    assert env.state.v == 0
    assert info["collisions"] == 1
    assert info["distance"] == 0
    assert info["reward_components"]["collision"] == -5
    assert reward < 0


def test_blocking_cell_prevents_crossing(env):
    env.reset(options={"blocked": True})
    env.state.x, env.state.y, env.state.theta = 4, 11, 0
    env.step(Action.AVANZAR)
    assert env.position == (4, 11)
    assert env.state.colisiones == 1


def test_sensor_measures_wall_rack_and_blockage(env):
    env.state.x, env.state.y = 2, 3
    assert env.sensor_distances()[2] == 1  # rack al este
    assert env.sensor_distances()[6] == 2  # pared oeste
    env.state.x, env.state.y = 4, 11
    normal = env.sensor_distances()[0]
    env.reset(options={"blocked": True})
    env.state.x, env.state.y = 4, 11
    assert env.sensor_distances()[0] == 1
    assert normal > 1


@pytest.mark.parametrize("action,cost", [(0, 0.8), (1, 0.2), (2, 0.2), (3, 0.1), (4, 0.2)])
def test_energy_and_time_per_action(env, action, cost):
    _, _, _, _, info = env.step(action)
    assert env.state.bateria == pytest.approx(100 - cost)
    assert env.state.tiempo == info["simulated_time"] == 1
    assert env.state.tiempo_restante == 249
    assert info["battery_used"] == pytest.approx(cost)
    assert info["reward_components"]["battery"] == pytest.approx(-0.02 * cost)


def test_turns_do_not_move_and_braking_stops(env):
    env.state.theta = 1
    env.step(Action.AVANZAR)
    assert env.position == (3, 11) and env.state.v == 1
    env.step(Action.GIRAR_IZQUIERDA)
    assert env.position == (3, 11) and env.state.theta == 0
    env.step(Action.GIRAR_DERECHA)
    assert env.position == (3, 11) and env.state.theta == 1
    env.step(Action.FRENAR)
    assert env.state.v == 0


@pytest.mark.parametrize("kind", ["far", "moving", "wrong_facing", "wrong_station"])
def test_invalid_pickup_does_not_change_mission_and_never_pays(env, kind):
    put_in_front(env, "P1")
    if kind == "far":
        env.state.x, env.state.y = env.layout.base
    elif kind == "moving":
        env.state.v = 1.0
    elif kind == "wrong_facing":
        env.state.theta = (env.state.theta + 1) % 4
    else:
        put_in_front(env, "P2")
    mission = (env.state.carga, env.state.pedido_actual, env.state.etapa, env.state.objetivo)
    _, reward, _, _, info = env.step(Action.CARGAR)
    assert (env.state.carga, env.state.pedido_actual, env.state.etapa, env.state.objetivo) == mission
    assert not env.picked_packages and not env.completed_packages
    assert info["invalid_interactions"] == 1
    assert reward < 0


def test_delivery_without_package_is_invalid(env):
    put_in_front(env, "DELIVERY")
    _, reward, _, _, info = env.step(Action.DESCARGAR)
    assert env.state.carga is None
    assert env.state.entregas == 0
    assert reward < 0 and info["reward_components"]["delivery"] == 0


def test_pickup_once_cannot_drop_or_duplicate(env):
    _, reward, _, _, info = pickup(env)
    assert env.state.carga == "P1"
    assert env.state.objetivo == "DELIVERY"
    assert env.picked_packages == {"P1"}
    assert info["reward_components"]["pickup"] == 10
    for _ in range(3):
        _, reward, _, _, info = env.step(Action.CARGAR)
        assert reward < 0
        assert info["reward_components"]["pickup"] == 0
        assert env.state.carga == "P1"


def test_wrong_carried_package_cannot_be_delivered(env):
    pickup(env)
    put_in_front(env, "DELIVERY")
    env.state.carga = "P2"  # Caso defensivo: estado inconsistente externo.
    _, reward, _, _, info = env.step(Action.DESCARGAR)
    assert env.state.entregas == 0 and not env.completed_packages
    assert env.state.carga == "P2" and reward < 0
    assert info["reward_components"]["delivery"] == 0


def test_delivery_is_permanent_and_cannot_be_rewarded_twice(env):
    pickup(env)
    put_in_front(env, "DELIVERY")
    _, _, terminated, _, info = env.step(Action.DESCARGAR)
    assert not terminated  # Aún falta P2.
    assert info["reward_components"]["delivery"] == 30
    assert env.completed_packages == {"P1"}
    assert env.state.carga is None and env.state.objetivo == "P2"
    for _ in range(3):
        _, reward, _, _, info = env.step(Action.DESCARGAR)
        assert reward < 0 and info["reward_components"]["delivery"] == 0
        assert env.state.entregas == 1
    put_in_front(env, "P1")
    _, reward, _, _, info = env.step(Action.CARGAR)
    assert reward < 0 and info["reward_components"]["pickup"] == 0
    assert env.completed_packages == {"P1"}


def test_target_switch_does_not_pay_fake_progress(env):
    _, _, _, _, info = pickup(env)
    assert info["reward_components"]["progress"] == 0
    put_in_front(env, "DELIVERY")
    _, _, _, _, info = env.step(Action.DESCARGAR)
    assert info["reward_components"]["progress"] == 0


@pytest.mark.parametrize("orders,blocked", [(1, False), (1, True), (2, False), (2, True)])
def test_heuristic_completes_full_mission(orders, blocked):
    environment = WarehouseRushEnv(orders, blocked)
    observation, _ = environment.reset(seed=301)
    policy = HeuristicPolicy()
    completed = []
    for _ in range(250):
        observation, reward, terminated, truncated, info = environment.step(policy.action(observation, environment))
        assert environment.observation_space.contains(observation)
        assert sum(info["reward_components"].values()) == pytest.approx(reward)
        if info["reward_components"]["delivery"]:
            completed.append(environment.packages[environment.state.pedido_actual - 1])
        if terminated or truncated:
            break
    assert terminated and not truncated and info["success"]
    assert info["end_reason"] == "success"
    assert info["deliveries"] == orders
    assert info["collisions"] == info["invalid_interactions"] == 0
    assert completed == list(environment.packages)
    assert info["reward_components"]["completion"] == 50
    assert observation[21] == 1 and observation[23] == 1
    before = environment.snapshot()
    with pytest.raises(RuntimeError):
        environment.step(Action.DESCARGAR)
    assert environment.snapshot() == before


def test_battery_exhaustion_is_termination():
    environment = WarehouseRushEnv(simulation=SimulationConfig(battery_capacity=0.8))
    environment.reset()
    _, _, terminated, truncated, info = environment.step(Action.AVANZAR)
    assert terminated and not truncated
    assert info["failure"] and info["end_reason"] == "battery_depleted"
    assert environment.state.bateria == pytest.approx(0)
    with pytest.raises(RuntimeError):
        environment.step(Action.FRENAR)


def test_time_limit_is_truncation():
    environment = WarehouseRushEnv(simulation=SimulationConfig(max_steps=2))
    environment.reset()
    assert environment.step(Action.FRENAR)[2:4] == (False, False)
    observation, _, terminated, truncated, info = environment.step(Action.FRENAR)
    assert truncated and not terminated
    assert info["end_reason"] == "time_limit" and not info["success"]
    assert observation[22] == 0


def test_unreachable_goal_is_effective_failure(env):
    env._fields[False, "P1"] = {}  # Emula un destino sin ruta, sin alterar el JSON base.
    _, _, terminated, truncated, info = env.step(Action.FRENAR)
    assert terminated and not truncated
    assert info["end_reason"] == "unreachable_target" and info["failure"]


def test_map_has_routes_and_blockage_requires_detour():
    layout = Layout.load()
    distances = layout.validate_routes()
    assert distances["blocked"]["P1"] > distances["normal"]["P1"]
    for blocked in (False, True):
        for station in layout.stations:
            field = layout.distance_field(station, blocked)
            assert layout.base in field
            for other in layout.stations:
                assert layout.approaches(other, blocked) <= field.keys()


def test_same_seed_and_actions_are_reproducible():
    environments = [WarehouseRushEnv(2, True), WarehouseRushEnv(2, True)]
    a, ai = environments[0].reset(seed=21)
    b, bi = environments[1].reset(seed=21)
    np.testing.assert_array_equal(a, b)
    assert ai == bi
    for action in np.random.default_rng(9).integers(5, size=100):
        left, right = [env.step(int(action)) for env in environments]
        np.testing.assert_array_equal(left[0], right[0])
        assert left[1:] == right[1:]


def test_useless_forward_backward_cycle_has_negative_net_reward(env):
    env.state.x, env.state.y, env.state.theta = 5, 6, 1
    before = env.position
    progress, total = 0.0, 0.0
    for action in [0, 2, 2, 0, 2, 2, 3]:
        _, reward, _, _, info = env.step(action)
        total += reward
        progress += info["reward_components"]["progress"]
    assert env.position == before
    assert env.state.theta == 1 and env.state.v == 0
    assert progress == pytest.approx(0)
    assert total < 0
    assert env.state.colisiones == 0


def test_shaping_uses_route_distance_not_euclidean(env):
    env.state.x, env.state.y, env.state.theta = 3, 11, 1
    # Alejarse en x de P1 permite entrar por el paso x=4: progreso de ruta positivo.
    _, _, _, _, info = env.step(Action.AVANZAR)
    assert env.position == (4, 11)
    assert info["reward_components"]["progress"] == pytest.approx(0.3)
    env.state.theta = 3
    _, _, _, _, info = env.step(Action.AVANZAR)
    assert info["reward_components"]["progress"] == pytest.approx(-0.3)


def test_reset_clears_mission_and_statistics(env):
    pickup(env)
    env.reset(seed=6)
    assert not env.picked_packages and not env.completed_packages
    assert env.state.bateria == 100 and env.state.carga is None
    assert env.state.entregas == env.state.tiempo == env.state.colisiones == 0
    assert env.state.objetivo == "P1" and env.state.recompensa_total == 0


def test_reward_parameters_are_configurable_without_logic_changes():
    environment = WarehouseRushEnv(rewards=replace(RewardConfig(), pickup=7.0))
    environment.reset()
    _, _, _, _, info = pickup(environment)
    assert info["reward_components"]["pickup"] == 7


@pytest.mark.parametrize("kwargs", [{"time": 0}, {"invalid_interaction": 1}, {"progress": -1}, {"pickup": float("nan")}])
def test_reward_configs_reject_profitable_invalid_events(kwargs):
    with pytest.raises(ValueError):
        RewardConfig(**kwargs)


def test_render_uses_actual_map_and_obstruction(env):
    text = env.render()
    assert len(text.splitlines()[0]) == env.layout.width
    assert all(symbol in text for symbol in ("#", "R", "1", "2", "D", ":", "^"))
    env.reset(options={"blocked": True})
    assert "X" in env.render()
