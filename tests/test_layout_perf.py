"""La BFS optimizada de `Layout.distance_field` devuelve exactamente lo mismo que la versión lenta de referencia."""
from collections import deque
from pathlib import Path
import time

import pytest

from envs import make_env
from envs.layout import Layout


def reference_distance_field(layout, station, blocked):
    """Implementación original: recorre con `neighbors()` (reconstruye los obstáculos en cada vecino)."""
    distances = {cell: 0 for cell in layout.approaches(station, blocked)}
    queue = deque(distances)
    while queue:
        current = queue.popleft()
        for neighbor in layout.neighbors(current, blocked):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


@pytest.mark.parametrize("path", sorted(Path("configs").glob("layout_v0.*.json")))
def test_distance_field_matches_the_slow_reference_on_every_station_and_blocked_state(path):
    layout = Layout.load(path)
    for blocked in (False, True):
        for station in layout.stations:
            assert layout.distance_field(station, blocked) == reference_distance_field(layout, station, blocked)


def test_makeup_environment_fields_match_the_reference_and_building_it_is_fast():
    start = time.perf_counter()
    env = make_env(layout_path="configs/layout_v0.4.json", orders=3)
    elapsed = time.perf_counter() - start
    for (blocked, station), field in env._fields.items():
        assert field == reference_distance_field(env.layout, station, blocked)
    assert elapsed < 1.5   # antes ≈ 2.6 s (4.6 s con perfilador); margen amplio para máquinas lentas o cargadas
