"""Evalúa un run con la política ESTOCÁSTICA (deterministic=False) en la suite del nivel, con su mapa y su recompensa.

Uso:
  .venv/bin/python -I .claude/skills/warehouse-rush/scripts/eval_stochastic.py <run> [--episodes 50] [--seed-start 10000] [--repeats 3]

Por qué existe: la suite oficial evalúa con la acción más probable (determinista). Una política que en
entrenamiento (estocástica) completa la misión pero en evaluación determinista no, queda escondida.
No sustituye a la evaluación oficial; es un diagnóstico. Salida: docs/resultados/eval/<run>/stochastic.json (stochastic-<seed-start>.json si la semilla inicial no es 10000).
Cada repetición usa otra semilla de muestreo (torch) sobre las mismas semillas de episodio.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402
from stable_baselines3.common.utils import set_random_seed  # noqa: E402

from envs import make_env  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    parser.add_argument("--episodes", type=int, default=50)
    parser.add_argument("--seed-start", type=int, default=10_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    meta = json.loads(Path(f"docs/resultados/training/{args.run}/metadata.json").read_text())
    model = PPO.load(f"models/{args.run}/model.zip", device="cpu")
    out = []
    for rep in range(args.repeats):
        set_random_seed(1000 + rep)
        rows = []
        for ep in range(args.episodes):
            env = make_env(layout_path=meta.get("layout_path"), orders=meta["orders"],
                           reward_overrides=meta.get("reward_overrides") or None)
            obs, _ = env.reset(seed=args.seed_start + ep)
            done = False
            while not done:
                action, _ = model.predict(obs, deterministic=False)
                obs, _, term, trunc, info = env.step(int(action))
                done = term or trunc
            rows.append(dict(success=bool(info["success"]), steps=info["steps"], deliveries=info["deliveries"],
                             end_reason=info["end_reason"], invalid=info["invalid_interactions"], collisions=info["collisions"]))
        ok = [r["steps"] for r in rows if r["success"]]
        out.append(dict(sampling_seed=1000 + rep, success_rate=len(ok) / len(rows),
                        mean_steps_of_successes=float(np.mean(ok)) if ok else None,
                        mean_deliveries=float(np.mean([r["deliveries"] for r in rows])),
                        mean_invalid=float(np.mean([r["invalid"] for r in rows])),
                        mean_collisions=float(np.mean([r["collisions"] for r in rows])),
                        end_reasons={k: sum(r["end_reason"] == k for r in rows) for k in {r["end_reason"] for r in rows}}))
        print(args.run, out[-1], flush=True)
    name = "stochastic.json" if args.seed_start == 10_000 else f"stochastic-{args.seed_start}.json"
    Path(f"docs/resultados/eval/{args.run}/{name}").write_text(json.dumps(
        dict(run=args.run, suite_seeds=f"{args.seed_start}-{args.seed_start + args.episodes - 1}", deterministic=False, repeats=out), indent=2) + "\n")


if __name__ == "__main__":
    main()
