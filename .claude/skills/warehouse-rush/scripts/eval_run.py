"""Evalúa un run entrenado en su propia suite, con SU mapa y SU recompensa (leídos de metadata.json).

Uso (desde cualquier carpeta):
  .venv/bin/python -I .claude/skills/warehouse-rush/scripts/eval_run.py m1o-e4l-seed0
  ... eval_run.py <run> [--episodes 50] [--seed-start 10000] [--policies heuristic ppo] [--output-dir DIR]

Por qué existe: `pipelines.evaluate.evaluate` no deduce el mapa ni los coeficientes de recompensa del run;
hay que pasarlos. Este script los toma de docs/resultados/training/<run>/metadata.json (campos
`layout_path`, `reward_overrides`, `orders`), de modo que el retorno y el mapa coinciden con el entrenamiento.
Salida por defecto: docs/resultados/eval/<run>/ (evaluation.json, evaluation.csv, report.md).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from pipelines.evaluate import evaluate  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", help="nombre del run, p. ej. m1o-e4l-seed0")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=10_000)
    parser.add_argument("--policies", nargs="+", default=["heuristic", "ppo"])
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    meta = json.loads(Path(f"docs/resultados/training/{args.run}/metadata.json").read_text())
    result = evaluate(policies=tuple(args.policies), orders=meta["orders"], episodes=args.episodes,
                      seed_start=args.seed_start, scenarios=(False,),
                      model_path=f"models/{args.run}/model.zip",
                      output_dir=args.output_dir or f"docs/resultados/eval/{args.run}",
                      layout_path=meta.get("layout_path"),
                      reward_overrides=meta.get("reward_overrides") or None)
    print(args.run, "completed:", result["completed"], "errors:", result["errors"])
    for row in result["summary"]:
        print(f"  {row['policy']:9s} success={100 * row['success_rate']:.0f}% return={row['mean_total_reward']:.1f} "
              f"steps={row['mean_steps']:.0f} pickups={row['mean_pickups']:.2f} deliveries={row['mean_deliveries']:.2f} "
              f"invalid/ep={row['mean_invalid_interactions']:.1f} end={row['end_reasons']}")


if __name__ == "__main__":
    main()
