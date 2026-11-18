"""Catálogo del PDF: cobertura de las seis categorías y conservación del picking de cada SKU operativo."""
from collections import Counter
import json
from pathlib import Path

import pytest
from gymnasium.utils.env_checker import check_env
from envs.inventory import CATALOG, Inventory
from envs.missions import MakeupMissionEnv
from envs.env import SimulationConfig, WarehouseRushEnv
from pipelines.baselines import HeuristicPolicy

PRODUCTS = json.loads((Path(__file__).resolve().parents[1] / "configs/products.json").read_text())


def test_pdf_selection_and_gymnasium_contract():
    assert Counter(p['category'] for p in PRODUCTS) == {
        'Maquillaje': 12, 'Cuidado de la piel': 4, 'Brochas': 2,
        'Accesorios': 3, 'Capilar': 3, 'Disney': 3,
    }
    assert all(not p['temporary'] and p['name'] and 1 <= p['source_page'] <= 7 for p in PRODUCTS)
    check_env(WarehouseRushEnv(), skip_render_check=True)


@pytest.mark.parametrize('sku', list(CATALOG))
@pytest.mark.parametrize('blocked', [False, True])
def test_each_operational_sku_can_be_picked_and_delivered(sku, blocked):
    inventory = Inventory({sku: CATALOG[sku]['initial_stock']})
    env = MakeupMissionEnv(inventory=inventory, blocked=blocked,
                          simulation=SimulationConfig(battery_capacity=300, max_steps=600))
    obs, _ = env.reset(seed=42)
    policy = HeuristicPolicy()
    while not env._done:
        obs, _, _, _, info = env.step(policy.action(obs, env))
    assert info['success'], (sku, info['end_reason'])
    line = info['state']['order']['lines'][0]
    assert line['level'] == CATALOG[sku]['level']
    assert line['delivered'] == line['quantity']
    assert inventory.total[sku] == CATALOG[sku]['initial_stock'] - line['quantity']
    assert line['name'] == CATALOG[sku]['name']
    assert info['collisions'] == 0
