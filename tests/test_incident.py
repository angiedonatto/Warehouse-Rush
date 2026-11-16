"""Incidente N3 del mapa con muro: nivel m1b ('mixto'), configs de la intervención i1 y entrenamiento mixto."""
import shutil
from pathlib import Path

import pytest
import yaml

from envs import make_env
from pipelines.train import training_env_blocked, train_ppo

WALLED = "configs/layout_v0.4.json"


def raw(name):
    return yaml.safe_load(Path(f"configs/experiments/{name}.yaml").read_text())


def test_mixed_blocking_alternates_closed_and_open_envs():
    assert [training_env_blocked(i, "mixto") for i in range(4)] == [True, False, True, False]
    assert training_env_blocked(3, True) is True and training_env_blocked(0, False) is False
    with pytest.raises(ValueError):
        training_env_blocked(0, "a veces")


def test_closed_gap_is_a_real_detour_and_still_solvable():
    env = make_env(blocked=True, layout_path=WALLED, orders=3)
    assert (6, 14) in env.layout.obstacles(True) and (6, 14) not in env.layout.obstacles(False)
    base = env.layout.base
    assert env.layout.distance_field("P1", True)[base] > env.layout.distance_field("P1", False)[base]
    for station in env.layout.stations:                      # todas las estaciones siguen alcanzables por x=20
        assert base in env.layout.distance_field(station, True)


def test_m1b_level_and_suite_match_m1_except_the_gap():
    levels = yaml.safe_load(Path("configs/niveles.yaml").read_text())
    assert levels["m1b"]["blocked"] == "mixto" and levels["m1b"]["orders"] == levels["m1"]["orders"]
    suite, normal = (yaml.safe_load(Path(f"configs/suites/{s}.yaml").read_text()) for s in ("suite-m1b-v1", "suite-m1-v1"))
    assert suite["semillas_rango"] == normal["semillas_rango"] and suite["episodios"] == normal["episodios"]


def test_i1_configs_are_c3_seed0_fine_tuned_on_m1b():
    c3 = raw("m1_c3_largo_seed0")
    for seed in (0, 1, 2):
        i1 = raw(f"m1b_i1_incidente_seed{seed}")
        assert i1["id"] == "i1" and i1["nivel"] == "m1b" and i1["seed"] == seed and i1["parent_run_id"] == "m1-c3-seed0"
        assert i1["evaluacion"]["final"] == "suite-m1b-v1"
        same = ("environment_version", "presupuesto_pasos", "parada_estancamiento", "layout", "recompensa", "ppo")
        assert {k: i1[k] for k in same} == {k: c3[k] for k in same}


def test_mixed_training_runs_and_records_the_scenario():
    run = "_test_incident_mixed"
    try:
        meta = train_ppo(timesteps=128, seed=986, orders=3, blocked="mixto", layout_path=WALLED, run_name=run, n_envs=2,
                         eval_every=128, eval_episodes=1, ppo=dict(n_steps=64, batch_size=64, ent_coef=0.0, net_arch=[64, 64]))
        assert meta["status"] == "completed" and meta["blocked"] == "mixto"
    finally:
        for path in (Path("models") / run, Path("docs/resultados/training") / run, Path("models/ppo_orders3_seed986.zip"),
                     Path("models/ppo_orders3_seed986.json")):
            shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True)
