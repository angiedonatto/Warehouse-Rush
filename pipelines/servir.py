"""Exporta los modelos que sirve la API (Vercel) a partir de sus manifiestos.

Por cada manifiesto `recomendado` compatible con el ambiente vigente:
- copia el peso a models/servidos/<modelo>.zip tras comprobar su SHA-256 (Git, ~200 KB; Vercel
  no tiene acceso a DVC);
- escribe su ficha en configs/modelos_servidos.json: identidad (run, manifiesto, MLflow, registro),
  estado, y la configuración EXACTA de evaluación (mapa, productos por pedido, recompensa), para que
  la web ejecute el modelo en el mismo ambiente con que se validó.

La API comprueba de nuevo el SHA-256 y la versión del ambiente al cargar. Nunca sobrescribe un peso
servido con otro contenido: un modelo nuevo es un archivo nuevo.

Uso: python -m pipelines.servir
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from envs import ENV_VERSION
from pipelines.tracking import sha256_file

SERVIDOS = Path("models/servidos")
FICHAS = Path("configs/modelos_servidos.json")
NIVELES = {"m1o": "N1 · mapa abierto", "m1": "N2 · mapa con muro", "m1b": "N3 · paso (6,14) cerrado"}
# Catálogo con que se certificaron (v10) y el que usa la web, con su diagnóstico (docs/resultados/eval/).
CATALOGO_EVALUACION, CATALOGO_WEB = "legacy-18", "trendy-27-v1"
DIAGNOSTICO_WEB = Path("docs/resultados/eval/catalogo-trendy-27/resultados.json")
REGISTRO = {"m1-c3-seed0": "warehouse-m1 v1", "m1b-i1-seed1-best": "warehouse-m1b v1"}


def resultados_ppo(bloque: dict | None) -> dict:
    """Éxito, pasos y choques del PPO por escenario, sin semillas ni rutas locales."""
    if not bloque:
        return {}
    escenarios = bloque.get("by_scenario") or {bloque.get("scenario", "abierto"): bloque.get("policies", {})}
    out = {}
    for nombre, politicas in escenarios.items():
        ppo = politicas.get("ppo") if isinstance(politicas, dict) else None
        if ppo:
            out[nombre] = {k: ppo[k] for k in ("success_rate", "mean_steps", "mean_collisions") if k in ppo}
    return {"suite": bloque.get("suite"), "episodes": bloque.get("episodes"), "met": bloque.get("met"),
            "criterion": bloque.get("criterion"), "ppo": out}


def ficha(nombre: str, m: dict, niveles: dict, diagnostico: dict) -> dict:
    return {
        "id": nombre, "run_id": m["run_id"], "level_id": m["level_id"],
        "nivel": NIVELES.get(m["level_id"], m["level_id"]), "estado": m["estado"],
        "environment_version": m["environment_version"], "algorithm": m.get("algorithm", "ppo"),
        "model_sha256": m["model_sha256"], "archivo": f"{SERVIDOS}/{nombre}.zip",
        "manifiesto": f"manifests/{nombre}.json", "git_commit": m["git_commit"],
        "layout_path": m["layout_path"], "layout_sha256": m["layout_sha256"],
        "orders": niveles[m["level_id"]]["orders"], "reward_overrides": m.get("reward_overrides") or {},
        "evaluation_suite_id": m["evaluation_suite_id"],
        "catalogo_evaluacion": CATALOGO_EVALUACION, "catalogo_web": CATALOGO_WEB,
        "diagnostico_catalogo_web": {k.split(" | ", 2)[2]: v for k, v in diagnostico.items()
                                     if k.startswith(CATALOGO_WEB) and f"| {nombre} |" in k},
        "evaluacion": resultados_ppo(m.get("evaluation")), "test_final": resultados_ppo(m.get("test_final")),
        "mlflow": {"tracking_uri": m.get("mlflow_tracking_uri"), "run_id": m.get("mlflow_run_id"),
                   "experiment": m.get("mlflow_experiment"), "registry": REGISTRO.get(nombre)},
    }


def main() -> None:
    niveles = yaml.safe_load(Path("configs/niveles.yaml").read_text())
    SERVIDOS.mkdir(parents=True, exist_ok=True)
    fichas = []
    for p in sorted(Path("manifests").glob("*.json")):
        if p.name == "schema.json":
            continue
        m = json.loads(p.read_text())
        if m.get("estado") != "recomendado" or m.get("environment_version") != ENV_VERSION:
            continue
        origen, destino = Path(m["model_uri"]), SERVIDOS / f"{p.stem}.zip"
        if sha256_file(origen) != m["model_sha256"]:
            raise SystemExit(f"{p.stem}: {origen} no coincide con model_sha256 (¿falta `dvc pull`?)")
        if destino.exists() and sha256_file(destino) != m["model_sha256"]:
            raise SystemExit(f"{destino} ya existe con otro contenido: un modelo nuevo necesita otro nombre")
        if not destino.exists():
            shutil.copyfile(origen, destino)
        fichas.append(ficha(p.stem, m, niveles, json.loads(DIAGNOSTICO_WEB.read_text())["resultados"]))
    # N3 primero: es el modelo de producción; N2 queda como rollback.
    fichas.sort(key=lambda f: (f["level_id"] != "m1b", f["id"]))
    FICHAS.write_text(json.dumps({"environment_version": ENV_VERSION, "modelos": fichas},
                                 indent=2, ensure_ascii=False) + "\n")
    print(f"{len(fichas)} modelos servidos: {', '.join(f['id'] for f in fichas)}")


if __name__ == "__main__":
    main()
