"""El visor no ofrece un PPO de otra familia de observaciones (experiment-001: 22; ambiente vigente: 27)."""
import secrets

import pytest

pytest.importorskip("stable_baselines3")

from api import _viewer  # noqa: E402
from api._cloud import CloudAPI  # noqa: E402
from envs import ENV_VERSION  # noqa: E402


def test_incompatible_ppo_is_not_offered_nor_served(monkeypatch):
    monkeypatch.setattr(_viewer, "viewer_model", lambda orders: _viewer.EXPERIMENT_MODEL)
    api = CloudAPI(secrets.token_urlsafe(48))
    layout, _ = api.handle("GET", "layout")
    assert layout["available_ppo"] == {"1": False, "2": False}
    with pytest.raises(ValueError, match="compatible"):
        api.handle("POST", "reset", {"orders": 1, "blocked": True, "policy": "ppo", "seed": 10000})
    assert api.handle("GET", "health")[0]["environment_version"] == ENV_VERSION
