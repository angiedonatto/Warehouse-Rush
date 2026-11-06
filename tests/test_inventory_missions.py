from concurrent.futures import ThreadPoolExecutor

import pytest
from warehouse_rush.inventory import CATALOG, Inventory
from warehouse_rush.missions import MakeupMissionEnv
from warehouse_rush.policies import HeuristicPolicy
from warehouse_rush.env import SimulationConfig
from warehouse_rush.viewer import ViewerSession

SKU = 'TMP-E01-L3'


def test_catalog_and_seed():
    assert len(CATALOG) == 18
    for i in range(1, 7):
        assert {p['level'] for p in CATALOG.values() if p['rack'] == f'E{i:02d}'} == {f'E{i:02d}-L{j}' for j in range(1, 4)}
    a, b = Inventory().generate(42), Inventory().generate(42)
    assert a['lines'] == b['lines']
    assert 1 <= len(a['lines']) <= 3
    assert all(1 <= l['quantity'] <= 3 for l in a['lines'])
    with pytest.raises(ValueError, match='sin stock'):
        Inventory({SKU: 0}).generate(1)


def test_atomic_reservation_and_concurrent_overselling():
    inv = Inventory({SKU: 5, 'TMP-E01-L1': 1})
    order = inv.reserve({SKU: 4, 'TMP-E01-L1': 2})
    assert order['state'] == 'REJECTED' and inv.available(SKU) == 5
    with ThreadPoolExecutor(2) as pool:
        orders = list(pool.map(lambda _: inv.reserve({SKU: 4}), range(2)))
    assert sorted(o['state'] for o in orders) == ['REJECTED', 'RESERVED']
    assert inv.total[SKU] == 5 and inv.available(SKU) == 1
    inv.check()


def test_exact_acceptance_duplicate_events_and_no_double_discount():
    inv = Inventory({SKU: 5})
    order = inv.reserve({SKU: 4}, 'acceptance')
    assert inv.reserve({SKU: 4}, 'acceptance') == order
    with pytest.raises(ValueError):
        inv.pick(order['id'], SKU, 5)
    assert inv.pick(order['id'], SKU, 4)
    assert not inv.pick(order['id'], SKU, 4)
    assert inv.total[SKU] == 1 and inv.reserved(SKU) == 0
    assert inv.deliver(order['id'], SKU)
    assert not inv.deliver(order['id'], SKU)
    assert inv.total[SKU] == 1
    inv.check()


def test_cancel_failure_and_pending_return():
    inv = Inventory({SKU: 5})
    a = inv.reserve({SKU: 4})
    assert inv.close(a['id']) and not inv.close(a['id'])
    assert inv.available(SKU) == 5
    b = inv.reserve({SKU: 4})
    inv.pick(b['id'], SKU, 4)
    inv.close(b['id'], failed=True)
    line = inv.orders[b['id']]['lines'][0]
    assert line['pending_return'] == 4 and inv.total[SKU] == 1
    with pytest.raises(ValueError):
        inv.deliver(b['id'], SKU)
    inv.check()


@pytest.mark.parametrize('blocked', [False, True])
@pytest.mark.parametrize('seed', range(12))
def test_navigable_orders_capacity_and_observation_contract(seed, blocked):
    # Presupuesto explícito para cubrir hasta tres viajes sin tocar defaults PPO.
    env = MakeupMissionEnv(blocked=blocked, simulation=SimulationConfig(battery_capacity=300, max_steps=600))
    obs, _ = env.reset(seed=seed)
    policy = HeuristicPolicy()
    while True:
        assert env.observation_space.contains(obs) and obs.shape == (22,)
        assert sum(l['quantity'] for l in env.snapshot()['cargo_lines']) <= env.capacity
        obs, _, done, truncated, info = env.step(policy.action(obs, env))
        assert env.position not in env._obstacles[blocked]
        env.inventory.check()
        if done or truncated:
            break
    assert info['success'], info['end_reason']
    assert info['collisions'] == 0
    assert info['state']['order']['state'] == 'DELIVERED'


def test_failure_with_cargo_remains_traceable():
    env = MakeupMissionEnv(simulation=SimulationConfig(max_steps=20))
    obs, _ = env.reset(seed=3)
    policy = HeuristicPolicy()
    while not env._done:
        obs, _, _, _, info = env.step(policy.action(obs, env))
    assert info['state']['order']['state'] == 'FAILED'
    assert sum(l['pending_return'] for l in info['state']['order']['lines']) > 0
    env.inventory.check()


def test_full_lip_order_robot_acceptance():
    # Un único SKU disponible fuerza un pedido válido de Labios.
    inv = Inventory({SKU: 5})
    env = MakeupMissionEnv(inventory=inv, capacity=4)
    # Semilla 0 selecciona cantidad 1..4 reproducible; localizar la que pide 4.
    seed = next(s for s in range(100) if Inventory({SKU: 5}).generate(s, 4)['lines'][0]['quantity'] == 4)
    obs, _ = env.reset(seed=seed)
    policy = HeuristicPolicy()
    while not env._done:
        obs, _, _, _, info = env.step(policy.action(obs, env))
    assert info['success'] and inv.total[SKU] == 1
    assert info['state']['order']['lines'][0]['delivered'] == 4
    print(f"ACEPTACIÓN Labios: inicial=5 reserva=4 recogida=4 entrega=4 final=1 pasos={info['steps']} colisiones={info['collisions']}")


def test_viewer_keeps_inventory_across_resets():
    session = ViewerSession(settings={'makeup': True, 'seed': 1})
    first = session.env.order_id
    session.reset({'makeup': True, 'seed': 2})
    assert session.inventory.orders[first]['state'] == 'CANCELLED'
    assert len(session.payload()['state']['inventory']['orders']) == 2


def test_cloud_makeup_roundtrip_and_inventory_retention():
    from warehouse_rush.cloud import CloudAPI
    secret = 'test-makeup-session-secret-32-characters'
    payload, token = CloudAPI(secret).handle('POST', 'reset', {'makeup': True, 'seed': 42, 'orders': 1})
    initial_id = payload['state']['order']['id']
    while not payload['done']:
        payload, token = CloudAPI(secret).handle('POST', 'step', {}, token)
        assert len(token) < 3800
    assert payload['info']['success']
    delivered = payload['state']['inventory']
    restored, _ = CloudAPI(secret).handle('GET', 'state', token=token)
    assert restored['state'] == payload['state']
    new, _ = CloudAPI(secret).handle('POST', 'reset', {'makeup': True, 'seed': 1}, token)
    assert {p['sku']: p['stock_total'] for p in new['state']['inventory']['products']} == {p['sku']: p['stock_total'] for p in delivered['products']}
    assert any(o['id'] == initial_id and o['state'] == 'DELIVERED' for o in new['state']['inventory']['orders'])


def test_makeup_ansi_and_reset_after_invalid_cookie():
    from warehouse_rush.cloud import CloudAPI
    env = MakeupMissionEnv(render_mode='ansi')
    env.reset(seed=1)
    assert 'E' in env.render()
    payload, token = CloudAPI('test-session-key-with-32-characters').handle('POST', 'reset', {'makeup': True}, 'invalid.cookie')
    assert payload['state']['tiempo'] == 0 and token


def test_collects_shelf_products_before_dispatch_when_capacity_allows():
    env = MakeupMissionEnv(blocked=True)
    obs, info = env.reset(seed=42)
    assert sum(l['quantity'] for l in env.lines) == 3
    policy = HeuristicPolicy()
    seen_targets = set()
    while not env._done:
        if env.state.etapa == 'recoger':
            seen_targets.add(env.state.objetivo)
        obs, _, _, _, info = env.step(policy.action(obs, env))
        if env.carried_lines and env.state.etapa == 'recoger':
            assert env.state.entregas == 0
        for line in info['state']['order']['lines']:
            assert env.inventory.total[line['sku']] == 5 - line['picked']
    events = info['state']['order']['events']
    pickups = [e['time'] for e in events if e['kind'].startswith('PICK:')]
    deliveries = [e['time'] for e in events if e['kind'].startswith('DELIVER:')]
    assert info['success'] and info['collisions'] == 0
    assert seen_targets == {l['rack'] for l in env.lines}
    assert max(pickups) < min(deliveries)
    assert len(set(deliveries)) == 1  # Un único despacho de las tres líneas.
    assert info['state']['cargo_lines'] == []


def test_batches_split_without_exceeding_capacity():
    env = MakeupMissionEnv(blocked=True)
    seed = next(s for s in range(100) if sum(l['quantity'] for l in Inventory().generate(s)['lines']) > 3)
    obs, _ = env.reset(seed=seed)
    policy = HeuristicPolicy()
    while not env._done:
        obs, _, _, _, info = env.step(policy.action(obs, env))
        assert sum(l['quantity'] for l in info['state']['cargo_lines']) <= 3
    assert info['success']
    assert len({e['time'] for e in info['state']['order']['events'] if e['kind'].startswith('DELIVER:')}) > 1
