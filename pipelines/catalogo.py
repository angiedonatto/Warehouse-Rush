"""Catálogo de modelos para la web, derivado de manifests/ + configs + MLflow (DagsHub).

Escribe web/public/modelos/catalogo.json (lo lee el diálogo «Modelos» de la web) y copia una versión
reducida de la curva de entrenamiento de cada run a web/public/modelos/curvas/<run>.png.
Cada entrada: identidad (run, nivel, semilla, estado, ambiente, hash), hipótesis y cambios frente a
la receta base, presupuesto, evaluación por política y escenario (éxito, pasos, choques, causas de
fin), decisión, test final, enlaces a MLflow y si la API puede ejecutarlo (configs/modelos_servidos.json).

Nada se escribe a mano: si un manifiesto cambia, se vuelve a generar.
Uso: python -m pipelines.catalogo
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

SALIDA = Path("web/public/modelos")
NIVELES = {"m1o": "N1 · mapa abierto", "m1": "N2 · mapa con muro", "m1b": "N3 · paso (6,14) cerrado",
           "n1": "v1 · N1 (historia)"}
TRACKING = "https://dagshub.com/mamezquita/Warehouse-Rush.mlflow"
# Receta base de PPO (configs de nivel): lo distinto se muestra como «cambio frente a la base».
PPO_BASE = {"learning_rate": 3.0e-4, "n_steps": 2048, "batch_size": 64, "n_epochs": 10, "gamma": 0.99,
            "gae_lambda": 0.95, "clip_range": 0.2, "ent_coef": 0.0, "net_arch": [64, 64]}
METRICAS = ("success_rate", "mean_steps", "mean_collisions", "mean_invalid_interactions", "mean_deliveries",
            "mean_total_reward", "end_reasons")


def escenarios(bloque: dict | None) -> dict:
    """{escenario: {política: métricas}} sin semillas ni rutas locales."""
    if not bloque:
        return {}
    crudo = bloque.get("by_scenario") or {bloque.get("scenario", "único"): bloque.get("policies", {})}
    return {nombre: {pol: {k: v for k, v in met.items() if k in METRICAS} for pol, met in politicas.items()}
            for nombre, politicas in crudo.items() if isinstance(politicas, dict)}


def experimentos_mlflow() -> dict:
    """Ids de experimento en el servidor para enlazar cada run (lectura pública)."""
    try:
        from mlflow.tracking import MlflowClient

        return {e.name: e.experiment_id for e in MlflowClient(os.environ.get("MLFLOW_TRACKING_URI", TRACKING)).search_experiments()}
    except Exception as exc:  # sin red: el catálogo sale igual, sin enlace directo al run
        print(f"aviso: sin acceso a MLflow ({type(exc).__name__}); enlaces solo al servidor")
        return {}


def curva(run: str) -> str | None:
    origen = next((p for p in (Path(f"docs/resultados/curvas/{run}.png"),
                               Path(f"docs/resultados/training/{run.removesuffix('-best')}/training_curve.png"))
                   if p.is_file()), None)
    if origen is None:
        return None
    from PIL import Image

    destino = SALIDA / "curvas" / f"{run}.png"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(origen) as img:
        img.thumbnail((960, 960))
        img.convert("RGB").quantize(colors=128).save(destino, optimize=True)
    return f"/modelos/curvas/{run}.png"


def entrada(nombre: str, m: dict, servidos: dict, exp_ids: dict) -> dict:
    config = yaml.safe_load(Path(m["config_uri"]).read_text()) if m.get("config_uri") and Path(m["config_uri"]).is_file() else {}
    ppo = config.get("ppo") or {}
    cambios = {"recompensa": m.get("reward_overrides") or config.get("recompensa") or {},
               "ppo": {k: v for k, v in ppo.items() if k in PPO_BASE and v != PPO_BASE[k]},
               "parada_estancamiento": config.get("parada_estancamiento"), "layout": config.get("layout"),
               "parent_run_id": m.get("parent_run_id")}
    exp = m.get("mlflow_experiment")
    run_url = (f"{TRACKING}/#/experiments/{exp_ids[exp]}/runs/{m['mlflow_run_id']}"
               if exp in exp_ids and m.get("mlflow_run_id") else TRACKING)
    return {
        "id": nombre, "run_id": m.get("run_id", nombre), "level_id": m.get("level_id"),
        "nivel": NIVELES.get(m.get("level_id"), m.get("level_id")), "estado": m.get("estado"),
        "seed": m.get("seed"), "environment_version": m.get("environment_version"),
        "algorithm": m.get("algorithm", "ppo"), "model_sha256": m.get("model_sha256"),
        "config_id": config.get("id"), "hipotesis": " ".join(str(config.get("hipotesis", "")).split()),
        "cambios": {k: v for k, v in cambios.items() if v not in (None, {}, [])},
        "presupuesto_pasos": m.get("budget_steps"), "minutos": m.get("budget_minutes"),
        "suite": m.get("evaluation_suite_id"), "evaluacion": escenarios(m.get("evaluation")),
        "test_final": escenarios(m.get("test_final")) if m.get("test_final") else None,
        "decision": m.get("decision_reason"), "manifiesto": f"manifests/{nombre}.json",
        "mlflow": {"run_url": run_url, "experimento": exp, "run_id": m.get("mlflow_run_id")},
        "curva": curva(nombre), "servido": nombre in servidos,
    }


def main() -> None:
    servidos = {s["id"]: s for s in json.loads(Path("configs/modelos_servidos.json").read_text())["modelos"]}
    exp_ids = experimentos_mlflow()
    modelos = []
    for p in sorted(Path("manifests").glob("*.json")):
        if p.name == "schema.json":
            continue
        m = json.loads(p.read_text())
        if not m.get("level_id") or not m.get("estado"):
            continue   # experiment-001: historia de la familia v1, sin evaluación comparable
        modelos.append(entrada(p.stem, m, servidos, exp_ids))
    orden = {"recomendado": 0, "candidato": 1, "rechazado": 2}
    modelos.sort(key=lambda e: (orden.get(e["estado"], 3), e["level_id"], e["id"]))
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "catalogo.json").write_text(json.dumps({"tracking_uri": TRACKING, "modelos": modelos},
                                                     ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{len(modelos)} modelos en {SALIDA / 'catalogo.json'}; curvas: {sum(bool(e['curva']) for e in modelos)}")


if __name__ == "__main__":
    main()
