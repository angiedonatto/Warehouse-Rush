"""Modelos servidos por la API: identidad verificada y el mismo comportamiento que en la evaluación.

La API en la nube reconstruye la sesión desde la cookie firmada en cada paso; la trayectoria debe ser
idéntica a ejecutar el modelo directamente en su ambiente de evaluación (make_env con su mapa, pedidos
y recompensa), si no la demo no mostraría el modelo que se validó.
"""
import json
import secrets
from pathlib import Path

import pytest

pytest.importorskip("stable_baselines3")

from api import _viewer  # noqa: E402
from api._cloud import CloudAPI  # noqa: E402
from api._viewer import ViewerSession  # noqa: E402
from envs import ENV_VERSION, make_env  # noqa: E402
from pipelines.baselines import make_policy  # noqa: E402
from pipelines.tracking import sha256_file  # noqa: E402

SPECS = json.loads(Path("configs/modelos_servidos.json").read_text())["modelos"]


def test_served_models_match_their_manifests():
    assert {s["id"] for s in SPECS} == {"m1-c3-seed0", "m1b-i1-seed1-best"}
    for spec in SPECS:
        manifest = json.loads(Path(spec["manifiesto"]).read_text())
        assert manifest["estado"] == spec["estado"] == "recomendado"
        assert spec["environment_version"] == manifest["environment_version"] == ENV_VERSION
        assert sha256_file(spec["archivo"]) == manifest["model_sha256"] == spec["model_sha256"]


@pytest.mark.parametrize("model_id,blocked,seed", [("m1-c3-seed0", False, 10003), ("m1b-i1-seed1-best", True, 10004)])
def test_cloud_episode_is_identical_to_direct_evaluation(model_id, blocked, seed):
    spec = next(s for s in SPECS if s["id"] == model_id)
    env = make_env(blocked, spec["layout_path"], spec["orders"], spec["reward_overrides"] or None)
    policy = make_policy("ppo", model_path=spec["archivo"])
    obs, _ = env.reset(seed=seed)
    direct, done = [], False
    while not done:
        obs, reward, terminated, truncated, info = env.step(policy.action(obs, env))
        direct.append((tuple(env.position), round(reward, 6)))
        done = terminated or truncated

    api = CloudAPI(secrets.token_urlsafe(48))
    state, token = api.handle("POST", "reset", {"policy": "ppo", "model": model_id, "blocked": blocked, "seed": seed})
    assert state["model"]["id"] == model_id and state["model"]["model_sha256"] == spec["model_sha256"]
    assert state["environment_version"] == ENV_VERSION
    cloud = []
    while not state["done"]:
        state, token = api.handle("POST", "step", {}, token)   # cada paso reconstruye desde la cookie
        cloud.append((tuple(state["trail"][-1]), round(state["last_reward"], 6)))
    assert [r for _, r in cloud] == [r for _, r in direct]
    assert cloud[-1][0] == direct[-1][0]
    assert state["info"]["success"] == info["success"]


def test_tampered_weights_are_refused(monkeypatch, tmp_path):
    fake = tmp_path / "x.zip"
    fake.write_bytes(b"no es el modelo")
    spec = {**SPECS[0], "archivo": str(fake)}
    monkeypatch.setattr(_viewer, "served_models", lambda: {spec["id"]: spec})
    _viewer._verified_model_path.cache_clear()
    try:
        session = ViewerSession()
        before = session.payload()
        with pytest.raises(ValueError, match="no coincide"):
            session.reset({"policy": "ppo", "model": spec["id"]})
        assert session.payload() == before   # la sesión vigente no se pierde
    finally:
        _viewer._verified_model_path.cache_clear()


def test_unknown_model_and_return_to_viewer_mission():
    session = ViewerSession()
    with pytest.raises(ValueError, match="desconocido"):
        session.reset({"policy": "ppo", "model": "no-existe"})
    session.reset({"policy": "ppo", "model": "m1-c3-seed0", "blocked": False, "seed": 1})
    assert session.payload()["model"]["id"] == "m1-c3-seed0"
    payload = session.reset({"policy": "heuristic", "makeup": True, "orders": 1, "blocked": False, "seed": 2})
    assert payload["model"] is None and payload["makeup"]
