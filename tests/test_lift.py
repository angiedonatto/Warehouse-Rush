import pytest

from envs.env import Action, SimulationConfig
from envs.handling import LEVEL_HEIGHTS
from envs.inventory import Inventory
from envs.missions import MakeupMissionEnv
from pipelines.baselines import HeuristicPolicy
from api._cloud import SignedSessions
from api._viewer import ViewerSession


def run_single_level(level):
    sku = f'TMP-E01-L{level}'
    env = MakeupMissionEnv(inventory=Inventory({sku: 1}))
    obs, _ = env.reset(seed=0)
    policy = HeuristicPolicy()
    saw_pickup = False
    while not env._done:
        pose = (*env.position, env.state.theta)
        phase = env.lift_phase
        obs, reward, _, _, info = env.step(policy.action(obs, env))
        if phase != 'idle':
            assert (*env.position, env.state.theta) == pose
        if env.carried_lines and not saw_pickup:
            assert env.lift_height == LEVEL_HEIGHTS[level - 1]
            assert env.inventory.total[sku] == 0
            saw_pickup = True
        elif not saw_pickup:
            assert env.inventory.total[sku] == 1
        assert sum(info['reward_components'].values()) == pytest.approx(reward)
    assert info['success'] and saw_pickup
    assert env.lift_height == env.lift_config.travel_height
    assert env.lift_phase == 'idle'
    assert env.dispatch_visits == 1
    assert env.state.colisiones == 0
    return info


def test_upper_levels_take_real_time_and_energy():
    results = [run_single_level(level) for level in (1, 2, 3)]
    assert results[0]['steps'] < results[1]['steps'] < results[2]['steps']
    assert results[0]['battery_used'] < results[1]['battery_used'] < results[2]['battery_used']
    assert all(r['state']['lift']['energy'] > 0 for r in results)


def raise_to(env, policy, obs, height):
    while env.lift_height != height:
        obs, _, _, _, _ = env.step(policy.action(obs, env))
    return obs


def test_cannot_reach_from_base_or_drive_with_lift_up():
    sku = 'TMP-E01-L3'
    env = MakeupMissionEnv(inventory=Inventory({sku: 1}))
    obs, _ = env.reset(seed=0)
    env.step(Action.SUBIR)   # desde BASE no mira a ningún estante: inválido
    assert env.lift_phase == 'idle' and env.inventory.total[sku] == 1
    assert env.state.interacciones_invalidas == 1
    policy = HeuristicPolicy()
    obs = raise_to(env, policy, obs, LEVEL_HEIGHTS[2])
    pose = (*env.position, env.state.theta)
    for action in (Action.AVANZAR, Action.GIRAR_IZQUIERDA, Action.GIRAR_DERECHA):
        env.step(action)
        assert (*env.position, env.state.theta) == pose
        assert env.state.v == 0
        assert env.inventory.total[sku] == 1
    assert env.blocked_lift_moves == 3
    env.step(Action.CARGAR)
    assert env.inventory.total[sku] == 0 and env.lift_phase == 'ready'   # la bandeja sigue arriba
    env.step(Action.DESCARGAR)                                           # no se descarga con la bandeja arriba
    assert env.state.entregas == 0 and env.carried_lines
    while env.lift_phase != 'idle':
        env.step(Action.BAJAR)
        assert (*env.position, env.state.theta) == pose
    assert env.inventory.total[sku] == 0


def test_lowering_before_pickup_preserves_stock_and_reservation():
    sku = 'TMP-E01-L3'
    env = MakeupMissionEnv(inventory=Inventory({sku: 1}))
    obs, _ = env.reset(seed=0)
    policy = HeuristicPolicy()
    raise_to(env, policy, obs, LEVEL_HEIGHTS[2])
    env.step(Action.FRENAR)        # frenar ya no aborta: la bandeja sigue arriba
    assert env.lift_phase == 'ready'
    while env.lift_phase != 'idle':
        env.step(Action.BAJAR)
    assert env.inventory.total[sku] == env.inventory.reserved(sku) == 1
    assert not env.carried_lines


def test_empty_robot_does_not_begin_unaffordable_mission():
    env = MakeupMissionEnv(simulation=SimulationConfig(max_steps=10))
    env.reset(seed=42)
    position = env.position
    _, _, done, truncated, info = env.step(Action.AVANZAR)
    assert done and not truncated and info['failure']
    assert info['end_reason'] == 'insufficient_budget'
    assert env.position == position
    assert sum(env.inventory.total.values()) == 90
    assert sum(env.inventory.reserved(s) for s in env.inventory.total) == 0


def test_loaded_robot_returns_before_trying_another_product_on_low_battery():
    env = MakeupMissionEnv()
    obs, _ = env.reset(seed=42)
    policy = HeuristicPolicy()
    line = env.lines[env.state.pedido_actual]
    raise_to(env, policy, obs, line['height_m'])
    env.state.bateria = 30.
    env.step(Action.CARGAR)
    assert env.carried_lines
    assert env.state.objetivo == 'DELIVERY'
    assert env.plan['reason'] == 'battery_or_time'
    assert env.lift_phase == 'ready'


@pytest.mark.parametrize('blocked', [False, True])
def test_nearby_lower_shelf_selected_before_distant_high_one(blocked):
    stock = {'TMP-E01-L3': 1, 'TMP-E04-L1': 1}
    seed = next(s for s in range(100) if len(Inventory(stock).generate(s)['lines']) == 2)
    env = MakeupMissionEnv(inventory=Inventory(stock), blocked=blocked)
    env.reset(seed=seed)
    assert env.state.objetivo == 'E04'
    assert env.plan['next_sku'] == 'TMP-E04-L1'


@pytest.mark.parametrize('phase', ['ready'])
def test_signed_snapshot_restores_mid_lift_without_stock_duplication(phase):
    session = ViewerSession(settings={'makeup': True, 'seed': 42})
    while session.env.lift_phase != phase:
        session.step()
    sessions = SignedSessions('unit-test-mechanism-key-with-32-characters')
    token = sessions.dump(session)
    assert len(token) < 3800
    restored = sessions.load(token)
    assert restored.payload() == session.payload()
    expected, actual = session.step(), restored.step()
    assert actual['state'] == expected['state']
    assert actual['last_action'] == expected['last_action']
    assert actual['last_reward'] == expected['last_reward']


def test_pre_lift_cookie_upgrades_level_metadata():
    import json
    import zlib
    import hmac
    from hashlib import sha256
    from base64 import urlsafe_b64decode, urlsafe_b64encode
    sessions = SignedSessions('unit-test-legacy-cookie-key-32-characters')
    session = ViewerSession(settings={'makeup': True, 'seed': 42})
    encoded = sessions.dump(session).split('.')[0]
    record = json.loads(zlib.decompress(urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))))
    record.pop('mechanism')
    for order in record['inventory']['orders'].values():
        for line in order['lines']:
            line.pop('height_m')
    encoded = urlsafe_b64encode(zlib.compress(json.dumps(record).encode())).decode().rstrip('=')
    token = encoded + '.' + hmac.new(sessions.key, encoded.encode(), sha256).hexdigest()
    restored = sessions.load(token)
    assert all('height_m' in l for l in restored.env.lines)
    assert restored.env.lift_phase == 'idle'
    assert restored.step()['state']['tiempo'] == 1


# --- Contrato v2: observación de 27 valores y acciones SUBIR/BAJAR/CARGAR/DESCARGAR ---

@pytest.mark.parametrize('level', [1, 2, 3])
def test_tray_moves_one_position_per_action(level):
    sku = f'TMP-E01-L{level}'
    env = MakeupMissionEnv(inventory=Inventory({sku: 1}))
    obs, _ = env.reset(seed=0)
    policy = HeuristicPolicy()
    ups = downs = 0
    while not env._done:
        action = policy.action(obs, env)
        ups += action == Action.SUBIR
        downs += action == Action.BAJAR
        obs, *_ = env.step(action)
    assert ups == downs == level           # una posición por acción: balda 3 = 3 SUBIR desde la posición de viaje


def test_observation_v2_layout():
    env = MakeupMissionEnv(inventory=Inventory({'TMP-E02-L3': 1}))
    obs, _ = env.reset(seed=0)
    w, h = env.layout.width - 1, env.layout.height - 1
    tx, ty = env.layout.stations[env.state.objetivo]
    assert obs.shape == (27,) and env.action_space.n == 8
    assert obs[8] == pytest.approx(env.state.x / w) and obs[9] == pytest.approx(env.state.y / h)
    assert obs[10] == pytest.approx(tx / w) and obs[11] == pytest.approx(ty / h)
    assert obs[24] == 0 and obs[25] == 0                       # lejos de todo, bandeja abajo
    assert obs[26] == pytest.approx(1.0)                        # balda 3 = elevación objetivo máxima
    env.state.x, env.state.y, env.state.theta, env.state.v = tx, ty + 2, 0, 0.   # al sur del estante, mirándolo
    env.state.y = ty + 1
    obs = env._observation()
    assert obs[24] == 1                                         # mira un objeto interactuable
    env.step(Action.SUBIR)
    assert env._observation()[25] == pytest.approx((.99 - .55) / (2.60 - .55))


def test_invalid_lift_and_load_actions_cost_and_change_nothing():
    sku = 'TMP-E01-L2'
    env = MakeupMissionEnv(inventory=Inventory({sku: 1}))
    obs, _ = env.reset(seed=0)
    for action in (Action.BAJAR, Action.SUBIR, Action.CARGAR, Action.DESCARGAR):
        _, reward, *_ = env.step(action)
        assert reward < 0 and env.lift_phase == 'idle'
    assert env.state.interacciones_invalidas == 4
    assert env.inventory.total[sku] == 1 and not env.carried_lines
    policy = HeuristicPolicy()
    raise_to(env, policy, obs, LEVEL_HEIGHTS[0])
    before = env.inventory.total[sku]
    env.step(Action.CARGAR)                                      # nivel equivocado: la balda es la 2
    assert env.inventory.total[sku] == before and not env.carried_lines
    while env.lift_height != LEVEL_HEIGHTS[2]:
        env.step(Action.SUBIR)
    n = env.state.interacciones_invalidas
    env.step(Action.SUBIR)                                       # ya está arriba del todo
    assert env.state.interacciones_invalidas == n + 1


def test_three_item_training_orders_differ_and_restock():
    from envs import make_env
    env = make_env(orders=3)
    seen = set()
    policy = HeuristicPolicy()
    for _ in range(6):
        obs, _ = env.reset()
        assert len(env.lines) == 3 and all(l['quantity'] == 1 for l in env.lines)
        seen.add(tuple(l['sku'] for l in env.lines))
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(policy.action(obs, env))
            done = term or trunc
        assert info['success']
    assert len(seen) > 1
    assert sum(env.inventory.total.values()) == 90 - 3          # stock repuesto en cada episodio
