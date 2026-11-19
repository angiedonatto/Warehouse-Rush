"""Caso del rollback que faltaba en el diagnóstico del catálogo: m1-c3-seed0 con el paso (6,14) cerrado.

m1-c3-seed0 es `produccion.anterior` (manifests/aliases.json): un rollback lo pone a servir. Los episodios de la web
usan el catálogo trendy-27-v1 (decisión de lis, 2026-11-18), así que se mide en trendy-27-v1 con el paso cerrado y
abierto, y en legacy-18 como control (debe reproducir la evaluación congelada: 0% cerrado, 98% abierto).
Determinista, semillas 10000-10049 (las de suite-m1-v1 / suite-m1b-v1); modelo del manifiesto con su sha256 verificado.

Uso (desde la raíz del repo): python docs/resultados/eval/catalogo-trendy-27/medir_rollback.py
Salida: docs/resultados/eval/catalogo-trendy-27/rollback_m1-c3-seed0.json
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
from envs import make_env  # noqa: E402
from pipelines import registry  # noqa: E402
from pipelines.baselines import make_policy  # noqa: E402

RUN = "m1-c3-seed0"
manifest = registry.cargar_manifiesto(RUN, RAIZ)
verificado = registry.verificar_modelo(RUN, descargar=True, raiz=RAIZ)
assert verificado["ok"], verificado
politica = make_policy("ppo", model_path=RAIZ / manifest["model_uri"])
resultado = {"run_id": RUN, "model_sha256": verificado["real"], "semillas": [10000, 10049], "determinista": True,
             "layout_path": manifest["layout_path"], "reward_overrides": manifest["reward_overrides"], "casos": {}}
for catalogo, bloqueado in (("trendy-27-v1", True), ("trendy-27-v1", False), ("legacy-18", True), ("legacy-18", False)):
    episodios = []
    for seed in range(10000, 10050):
        env = make_env(bloqueado, str(RAIZ / manifest["layout_path"]), 3, manifest["reward_overrides"], catalog=catalogo)
        obs, _ = env.reset(seed=seed)
        fin = False
        while not fin:
            obs, _, terminado, truncado, info = env.step(politica.action(obs, env))
            fin = terminado or truncado
        episodios.append({"seed": seed, "success": info["success"], "end_reason": info["end_reason"], "steps": info["steps"],
                          "collisions": info["collisions"], "deliveries": info["deliveries"]})
    exitos = [e for e in episodios if e["success"]]
    causas = {}
    for e in episodios:
        causas[e["end_reason"]] = causas.get(e["end_reason"], 0) + 1
    clave = f"{catalogo} | {'cerrado' if bloqueado else 'abierto'}"
    resultado["casos"][clave] = {
        "exito": len(exitos) / 50, "choques_ep": sum(e["collisions"] for e in episodios) / 50,
        "entregas_ep": sum(e["deliveries"] for e in episodios) / 50,
        "pasos_exito": round(sum(e["steps"] for e in exitos) / len(exitos), 1) if exitos else None,
        "causas": dict(sorted(causas.items())), "episodios": episodios}
    print(clave, {k: v for k, v in resultado["casos"][clave].items() if k != "episodios"}, flush=True)
salida = Path(__file__).with_name(f"rollback_{RUN}.json")
salida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n")
print("escrito", salida.relative_to(RAIZ))
