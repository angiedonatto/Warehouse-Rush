"""pipelines/compare.py: la semilla de entrenamiento es la unidad, la regla pre-registrada se aplica tal cual
y las curvas separan entrenamiento (estocástico) y evaluación (determinista)."""
import csv
import json

import numpy as np
import pytest
import yaml

from pipelines import compare as cmp

FIELDS = ["policy", "scenario", "seed", "success", "end_reason", "steps", "collisions",
          "invalid_interactions", "deliveries", "pickups"]


def fake_run(tmp_path, run, rate, overrides, seed=0, n=10, policy="ppo", parent=None):
    eval_dir = tmp_path / "eval" / run
    eval_dir.mkdir(parents=True)
    with (eval_dir / "evaluation.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        for i in range(n):
            ok = i < round(rate * n)
            writer.writerow({"policy": policy, "scenario": "normal", "seed": 10_000 + i, "success": str(ok),
                             "end_reason": "success" if ok else "time_limit", "steps": 90 if ok else 400,
                             "collisions": 0, "invalid_interactions": 1, "deliveries": 3 if ok else 0,
                             "pickups": 3 if ok else 0})
    train_dir = tmp_path / "train" / run
    train_dir.mkdir(parents=True)
    meta = {"seed": seed, "effective_timesteps": 1000, "duration_seconds": 600, "reward_overrides": overrides,
            "n_envs": 2, "parent_model": f"models/{parent}/model.zip" if parent else None}
    (train_dir / "metadata.json").write_text(json.dumps(meta))
    with (train_dir / "episodes.monitor.csv").open("w") as handle:
        handle.write('#{"t_start": 0}\nr,l,t,success\n')
        for i in range(50):
            handle.write(f"{i},{20},{i},{i > 25}\n")
    (train_dir / "periodic_eval").mkdir()
    np.savez(train_dir / "periodic_eval" / "evaluations.npz", timesteps=np.arange(1, 6) * 200,
             results=np.arange(25, dtype=float).reshape(5, 5), ep_lengths=np.ones((5, 5)))
    return run


@pytest.fixture
def roots(tmp_path):
    return {"eval_root": tmp_path / "eval", "train_root": tmp_path / "train"}


def test_each_training_seed_weighs_the_same(tmp_path, roots):
    runs = [fake_run(tmp_path, f"a-seed{i}", r, {"x": 1}, seed=i) for i, r in enumerate((1.0, 0.0, 0.0))]
    summary = cmp.recipe_summary("a", runs, 0.5, **roots)
    assert summary["mean_success"] == pytest.approx(1 / 3)
    assert summary["seeds_at_threshold"] == 1 and summary["n_seeds"] == 3
    lo, hi = summary["ci95_mean_success"]
    assert 0.0 <= lo <= 1 / 3 <= hi <= 1.0


def test_bootstrap_is_reproducible():
    assert cmp.bootstrap_mean_ci([0, 0, 1, 0.8]) == cmp.bootstrap_mean_ci([0, 0, 1, 0.8])


def _recipe(name, seeds_ok, mean, terms):
    return {"recipe": name, "seeds_at_threshold": seeds_ok, "mean_success": mean,
            "runs": [{"reward_overrides": {f"t{i}": 1 for i in range(terms)}}]}


def test_rule_picks_higher_mean_only_when_distinguishable():
    rule = {"margen_semillas": 1}
    clear = cmp.decide([_recipe("simple", 0, 0.0, 2), _recipe("rica", 3, 0.6, 4)], rule)
    assert clear == {**clear, "selected": "rica", "distinguishable": True}
    close = cmp.decide([_recipe("simple", 1, 0.2, 2), _recipe("rica", 2, 0.3, 4)], rule)
    assert close["selected"] == "simple" and not close["distinguishable"]


def test_recipe_must_share_reward_across_seeds():
    bad = _recipe("x", 1, 0.2, 2)
    bad["runs"].append({"reward_overrides": {"otro": 1}})
    with pytest.raises(ValueError, match="no es una receta"):
        cmp.decide([bad, _recipe("y", 1, 0.2, 2)], {"margen_semillas": 1})


def test_compare_writes_report_baselines_and_separate_curves(tmp_path, roots):
    a = [fake_run(tmp_path, f"a-seed{i}", r, {"x": 1}, seed=i) for i, r in enumerate((1.0, 0.0, 0.0))]
    b = [fake_run(tmp_path, f"b-seed{i}", r, {"x": 1, "y": 2}, seed=i) for i, r in enumerate((1.0, 0.9, 0.0))]
    base = tmp_path / "eval" / "base"
    base.mkdir()
    rows = list(csv.DictReader((tmp_path / "eval" / "a-seed1" / "evaluation.csv").open()))
    with (base / "evaluation.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "policy": "random"})
    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"id": "prueba", "suite": "s", "linea_base_run": "base",
                                      "finalistas": {"a": {"runs": a}, "b": {"runs": b}},
                                      "regla": {"umbral_exito_semilla": 0.5, "margen_semillas": 1}}))
    result = cmp.compare(config, output_root=tmp_path / "out", **roots)
    assert result["decision"]["selected"] == "a"  # 1 frente a 2 semillas: no distinguible, menos términos
    assert result["baselines"]["random"]["success_rate"] == 0.0
    out = tmp_path / "out" / "prueba"
    assert "Decisión (regla pre-registrada)" in (out / "report.md").read_text()
    assert sorted(p.name for p in (out / "curvas").iterdir()) == sorted(f"{r}.png" for r in a + b)


def test_curves_offset_continuations_by_the_parent_budget(tmp_path, roots):
    parent = fake_run(tmp_path, "padre", 1.0, {})
    child = fake_run(tmp_path, "hijo", 1.0, {}, parent="padre")
    _, steps, offset = cmp.training_episodes(parent, roots["train_root"])
    assert offset == 0 and steps[-1] == 50 * 20
    _, steps, offset = cmp.training_episodes(child, roots["train_root"])
    assert offset == 1000 and steps[0] == 1000 + 20 and steps[-1] == 1000 + 50 * 20
    assert cmp.plot_learning_curves(child, tmp_path / "c.png", train_root=roots["train_root"])
    assert (tmp_path / "c.png").stat().st_size > 0
