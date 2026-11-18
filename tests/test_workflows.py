import csv
import json

import pytest

from warehouse_rush.cli import demo_transitions, main
from warehouse_rush.evaluate import evaluate


def test_demo_contains_real_contiguous_step_results():
    rows = demo_transitions()
    assert len(rows) == 5
    assert rows[0]["resulting_state"]["colisiones"] == 1
    assert rows[2]["resulting_state"]["x"] == 3
    assert rows[3]["resulting_state"]["v"] == 0
    assert rows[4]["resulting_state"]["interacciones_invalidas"] == 1
    for previous, current in zip(rows, rows[1:]):
        assert previous["new_observation"] == current["observation"]
    for row in rows:
        assert row["reward"] == pytest.approx(sum(row["reward_components"].values()))
        assert row["resulting_state"]["tiempo"] == row["step"]


def test_evaluation_paired_seeds_and_csv_match_real_aggregates(tmp_path):
    result = evaluate(policies=("random", "heuristic"), episodes=2, output_dir=tmp_path)
    assert result["completed"]
    assert len(result["episodes"]) == 8
    assert len(result["summary"]) == 4
    for policy in ("random", "heuristic"):
        for scenario in ("normal", "blocked"):
            rows = [r for r in result["episodes"] if r["policy"] == policy and r["scenario"] == scenario]
            assert [r["seed"] for r in rows] == [10_000, 10_001]
            summary = next(s for s in result["summary"] if s["policy"] == policy and s["scenario"] == scenario)
            assert summary["mean_total_reward"] == pytest.approx(sum(r["total_reward"] for r in rows) / 2)
            if policy == "heuristic":
                assert summary["success_rate"] == 1
    with (tmp_path / "evaluation.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 8
    saved = json.loads((tmp_path / "evaluation.json").read_text())
    assert saved == result
    assert "Hechos medidos" in (tmp_path / "report.md").read_text()


def test_failed_evaluation_records_error_and_is_not_success(tmp_path):
    (tmp_path / "evaluation.csv").write_text("stale,data\nprior,run\n")
    result = evaluate(policies=("ppo",), episodes=1,
                      model_path=tmp_path / "missing.zip", output_dir=tmp_path)
    assert not result["completed"]
    assert len(result["errors"]) == 2
    assert all("FileNotFoundError" in error["error"] for error in result["errors"])
    assert not result["episodes"]
    with (tmp_path / "evaluation.csv").open() as handle:
        assert list(csv.DictReader(handle)) == []
    assert "incompleta" in (tmp_path / "report.md").read_text()


def test_cli_map_and_nonvisual_play(capsys):
    main(["map", "--blocked"])
    assert "X" in capsys.readouterr().out
    main(["play", "--policy", "heuristic", "--orders", "2", "--blocked", "--no-render"])
    info = json.loads(capsys.readouterr().out)
    assert info["success"] and info["deliveries"] == 2
