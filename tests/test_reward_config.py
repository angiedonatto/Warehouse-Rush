"""Recompensa v3: coeficientes por run, validación y que explorar acciones inválidas nunca sea rentable."""
from dataclasses import asdict

import pytest

from envs import ENV_VERSION, make_env, reward_config
from envs.env import Action
from envs.rewards import RewardConfig
from pipelines.train import load_config


def test_default_reward_equals_v2_coefficients():
    assert asdict(reward_config()) == {"pickup": 10.0, "delivery": 30.0, "completion": 50.0, "progress": 0.3,
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
        config = load_config(f"configs/experiments/{name}.yaml")
        assert list(config["recompensa"]) == ["invalid_interaction"]
        assert -2.0 < config["recompensa"]["invalid_interaction"] < 0
    assert "recompensa" not in load_config("configs/experiments/m1_c0b_control_v3.yaml")
