"""Diagnóstico de una política entrenada: dónde termina cada episodio y qué elige en los estados clave.

Uso:
  .venv/bin/python -I .claude/skills/warehouse-rush/scripts/trace_policy.py m1o-e4l-seed0 [--seed-start 10000 --episodes 50]

Repite los episodios de la suite con la acción MÁS PROBABLE (= predicción determinista de PPO) y reporta:
  - clase del estado final (bandeja arriba con/sin carga, frente al estante parado, en celda de interacción sin
    mirar, sin llegar, éxito);
  - en cuántos episodios llegó a una celda de interacción del primer objetivo y cuándo miró al estante;
  - para los estados clave, la acción elegida y las probabilidades medias de las 8 acciones:
      S  = parado, mirando al estante objetivo, bandeja abajo        (¿pulsa SUBIR?)
      R  = bandeja arriba pero por debajo de la altura necesaria      (¿sigue subiendo?)
      R2 = bandeja justo a la altura necesaria, sin carga todavía     (¿pulsa CARGAR?)
      AP = ya cargó y la bandeja sigue arriba                         (¿pulsa BAJAR?)
Sirve para distinguir un colapso a FRENAR, una evitación del estante, un giro en el sitio, un bucle de acciones
inválidas o una parada tras cargar (lo que ocurrió en los runs m1o-d2, e2, e3, e4, e5 y e4l).
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from stable_baselines3 import PPO  # noqa: E402

from envs import make_env  # noqa: E402
from envs.env import Action  # noqa: E402

NAMES = [a.name for a in Action]


def probabilities(model, obs):
    with torch.no_grad():
        return model.policy.get_distribution(model.policy.obs_to_tensor(obs)[0]).distribution.probs[0].numpy()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run")
    parser.add_argument("--seed-start", type=int, default=10_000)
    parser.add_argument("--episodes", type=int, default=50)
    args = parser.parse_args()
    meta = json.loads(Path(f"docs/resultados/training/{args.run}/metadata.json").read_text())
    env = make_env(layout_path=meta.get("layout_path"), orders=meta["orders"],
                   reward_overrides=meta.get("reward_overrides") or None)
    model = PPO.load(f"models/{args.run}/model.zip", device="cpu")
    finals, key = collections.Counter(), {k: (collections.Counter(), []) for k in ("S", "R", "R2", "AP")}
    reached = faced = raised = loaded = 0
    for seed in range(args.seed_start, args.seed_start + args.episodes):
        obs, _ = env.reset(seed=seed)
        approaches = env.layout.approaches(env.state.objetivo)
        done, hit_cell, hit_face, hit_raise, hit_load = False, False, False, False, False
        while not done:
            probs = probabilities(model, obs)
            action = int(np.argmax(probs))
            level, needed, st = env.tray_level(), env.needed_tray_level(), env.state
            looking = st.etapa == "recoger" and env.facing_target()
            state = ("S" if looking and st.v == 0 and level == 0 else
                     "R" if looking and 0 < level < needed else
                     "R2" if looking and level == needed > 0 and not env.carried_lines else
                     "AP" if env.carried_lines and level > 0 else None)
            if state:
                key[state][0][NAMES[action]] += 1
                key[state][1].append(probs)
            obs, _, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            hit_cell |= env.position in approaches
            hit_face |= env.facing_target()
            hit_raise |= env.lift_phase != "idle"
            hit_load |= bool(env.carried_lines)
        reached, faced, raised, loaded = reached + hit_cell, faced + hit_face, raised + hit_raise, loaded + hit_load
        tray = "bandeja arriba" if env.lift_phase != "idle" else "bandeja abajo"
        load = "con carga" if env.carried_lines else "sin carga"
        finals[f"{'éxito' if info['success'] else info['end_reason']} / {tray} / {load}"] += 1
    n = args.episodes
    print(f"{args.run}: {n} episodios (semillas {args.seed_start}-{args.seed_start + n - 1})")
    print(f"  llegó a una celda de interacción del 1.er objetivo: {reached}/{n} | miró al estante: {faced}/{n} | "
          f"subió la bandeja: {raised}/{n} | cargó algo: {loaded}/{n}")
    print("  estado final:")
    for label, count in finals.most_common():
        print(f"    {count:3d}  {label}")
    for name, (chosen, plist) in key.items():
        if plist:
            mean = {a: round(float(p), 3) for a, p in zip(NAMES, np.mean(plist, axis=0))}
            print(f"  estado {name}: acciones elegidas {dict(chosen)} | probabilidades medias {mean}")
        else:
            print(f"  estado {name}: nunca visitado")


if __name__ == "__main__":
    main()
