"""Diagnóstico: modelos recomendados con el catálogo de v10 (legacy-18) y el de la web (trendy-27-v1).

Uso: python docs/resultados/eval/catalogo-trendy-27/medir_catalogo.py   (desde la raíz del repo)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from envs import make_env  # noqa: E402
from pipelines.baselines import make_policy  # noqa: E402

SPECS = {s["id"]: s for s in json.loads(Path("configs/modelos_servidos.json").read_text())["modelos"]}
out = {}
for catalogo in ("legacy-18", "trendy-27-v1"):
    for mid, blocked in (("m1-c3-seed0", False), ("m1b-i1-seed1-best", False), ("m1b-i1-seed1-best", True)):
        s = SPECS[mid]
        pol = make_policy("ppo", model_path=s["archivo"])
        ok = steps = col = 0
        for seed in range(10000, 10050):
            env = make_env(blocked, s["layout_path"], s["orders"], s["reward_overrides"] or None, catalog=catalogo)
            o, _ = env.reset(seed=seed)
            done = False
            while not done:
                o, r, te, tr, info = env.step(pol.action(o, env))
                done = te or tr
            ok += info["success"]
            col += env.state.colisiones
            steps += env.state.tiempo if info["success"] else 0
        key = f"{catalogo} | {mid} | {'cerrado' if blocked else 'abierto'}"
        out[key] = dict(exito=ok / 50, pasos_exito=round(steps / max(ok, 1), 1), choques_ep=col / 50)
        print(key, out[key], flush=True)
