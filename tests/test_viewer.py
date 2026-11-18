from functools import partial
from http.server import ThreadingHTTPServer
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from envs.env import WarehouseRushEnv
from pipelines.baselines import HeuristicPolicy
from api._viewer import ViewerHandler, ViewerSession


@pytest.mark.parametrize("orders,blocked", [(1, False), (1, True), (2, False), (2, True)])
def test_viewer_steps_are_identical_to_python_environment(orders, blocked):
    session = ViewerSession()
    payload = session.reset({"orders": orders, "blocked": blocked, "policy": "heuristic"})
    reference = WarehouseRushEnv(orders, blocked)
    observation, _ = reference.reset(seed=10000)
    policy = HeuristicPolicy()
    while not payload["done"]:
        action = policy.action(observation, reference)
        observation, reward, terminated, truncated, info = reference.step(action)
        payload = session.step()
        assert payload["state"] == reference.snapshot()
        assert payload["last_action"]["code"] == action
        assert payload["last_reward"] == reward
        assert payload["observation"] == observation.tolist()
        assert payload["terminated"] == terminated and payload["truncated"] == truncated
    assert payload["info"]["success"] and payload["state"]["entregas"] == orders
    assert payload["route"] == []
    assert payload["events"][-1]["text"] == "Misión completada"
    with pytest.raises(ValueError, match="terminó"):
        session.step()


def test_manual_actions_and_invalid_reset_preserve_real_state():
    session = ViewerSession()
    session.reset({"policy": "manual", "orders": 1, "blocked": False})
    with pytest.raises(ValueError, match="manual"):
        session.step()
    payload = session.step(0)  # Pared interior frente a BASE.
    assert payload["state"]["colisiones"] == 1
    assert payload["state"]["x"] == 2 and payload["state"]["y"] == 11
    before = session.payload()
    with pytest.raises(ValueError):
        session.reset({"orders": 3})
    assert session.payload() == before
    with pytest.raises(ValueError):
        session.step(1.5)
    assert session.payload() == before


def test_reference_route_respects_same_map_and_blockage():
    session = ViewerSession()
    normal = session.reset({"orders": 1, "blocked": False})
    blocked = session.reset({"orders": 1, "blocked": True})
    assert len(blocked["route"]) > len(normal["route"])
    assert [4, 10] in normal["route"] and [4, 10] not in blocked["route"]
    for coordinate in blocked["route"]:
        assert session.env.layout.free(tuple(coordinate), True)
    assert tuple(blocked["route"][-1]) in session.env.layout.approaches("P1", True)
    assert session.layout_payload()["layout_sha256"] == session.env.layout.digest
    assert blocked["route_kind"] == "bfs_reference"


def test_missing_ppo_does_not_destroy_current_session(tmp_path, monkeypatch):
    monkeypatch.setattr("api._viewer.default_model", lambda order: tmp_path / "absent.zip")
    monkeypatch.setattr("api._viewer.EXPERIMENT_MODEL", tmp_path / "absent.zip")
    session = ViewerSession()
    before = session.payload()
    with pytest.raises(FileNotFoundError):
        session.reset({"policy": "ppo", "orders": 1})
    assert session.payload() == before
    assert session.layout_payload()["available_ppo"] == {"1": False, "2": False}


def test_http_routes_serve_real_state_and_validation_errors(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Warehouse Rush</h1>")
    session = ViewerSession()
    handler = partial(ViewerHandler, session=session, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def post(path, body, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        return urlopen(Request(base + path, json.dumps(body).encode(), headers), timeout=10)

    try:
        assert b"Warehouse Rush" in urlopen(base).read()
        payload = json.loads(urlopen(base + "/api/state").read())
        assert payload["state"]["tiempo"] == 0
        with post("/api/step", {}) as response:
            assert json.loads(response.read())["state"]["tiempo"] == 1
        with pytest.raises(HTTPError) as rejected:
            post("/api/reset", {"orders": 3})
        assert rejected.value.code == 400
        with pytest.raises(HTTPError) as rejected:
            post("/api/step", {}, origin="https://unrelated.example")
        assert rejected.value.code == 403
        assert json.loads(urlopen(base + "/api/state").read())["state"]["tiempo"] == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
