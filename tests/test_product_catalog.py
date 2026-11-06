"""Catálogo del PDF: cobertura de las seis categorías y picking de cada SKU."""
from collections import Counter

import pytest
from gymnasium.utils.env_checker import check_env
from warehouse_rush.inventory import CATALOG, Inventory
from warehouse_rush.missions import MakeupMissionEnv
from warehouse_rush.env import SimulationConfig, WarehouseRushEnv
from warehouse_rush.policies import HeuristicPolicy


def test_pdf_selection_and_gymnasium_contract():
    assert Counter(p['category'] for p in CATALOG.values()) == {
        'Maquillaje': 12, 'Cuidado de la piel': 4, 'Brochas': 2,
        'Accesorios': 3, 'Capilar': 3, 'Disney': 3,
    }
    assert all(not p['temporary'] and p['name'] and 1 <= p['source_page'] <= 7 for p in CATALOG.values())
    check_env(WarehouseRushEnv(), skip_render_check=True)


@pytest.mark.parametrize('sku', list(CATALOG))
@pytest.mark.parametrize('blocked', [False, True])
def test_each_selected_product_can_be_picked_and_delivered(sku, blocked):
    inventory = Inventory({sku: 5})
    env = MakeupMissionEnv(inventory=inventory, blocked=blocked,
                          simulation=SimulationConfig(battery_capacity=300, max_steps=600))
    obs, _ = env.reset(seed=42)
    policy = HeuristicPolicy()
    while not env._done:
        obs, _, _, _, info = env.step(policy.action(obs, env))
    assert info['success'], (sku, info['end_reason'])
    line = info['state']['order']['lines'][0]
    assert line['name'] == CATALOG[sku]['name']
    assert line['delivered'] == line['quantity']
    assert inventory.total[sku] == 5 - line['quantity']
    assert info['collisions'] == 0
