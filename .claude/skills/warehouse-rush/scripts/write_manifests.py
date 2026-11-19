"""Escribe manifests/<run>.json y la etiqueta MLflow `estado` para runs ya entrenados y evaluados.

Uso (desde cualquier carpeta):
  .venv/bin/python -I .claude/skills/warehouse-rush/scripts/write_manifests.py decisiones.json

decisiones.json:
  {"m1-c4-seed1": {"estado": "rechazado",
                   "reason": "Receta ... 0% de éxito; 0/50 llegan ...; criterio ...",
                   "config": "m1_c4_entropia_seed1"},
   ...}
`estado` ∈ candidato | recomendado | rechazado | fallido | interrumpido. `config` es el nombre del YAML sin extensión.
Requiere: docs/resultados/training/<run>/metadata.json, docs/resultados/eval/<run>/evaluation.json (de eval_run.py),
models/<run>/model.zip, y el run en MLflow (experimento warehouse-<nivel>). Valida contra manifests/schema.json.
Plantilla: manifests/m1o-e4l-seed1.json (claves fijas del esquema); los campos específicos se rellenan desde metadata.json.
"""
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import mlflow  # noqa: E402
from jsonschema import validate  # noqa: E402
from mlflow.tracking import MlflowClient  # noqa: E402

from envs import ENV_VERSION  # noqa: E402

TEMPLATE = "manifests/m1o-e4l-seed1.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(decisions_path):
    decisions = json.loads(Path(decisions_path).read_text())
    from pipelines.tracking import tracking_uri
    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient()
    schema = json.loads(Path("manifests/schema.json").read_text())
    template = json.loads(Path(TEMPLATE).read_text())
    for run, d in decisions.items():
        level = run.split("-")[0]
        meta = json.loads(Path(f"docs/resultados/training/{run}/metadata.json").read_text())
        ev = json.loads(Path(f"docs/resultados/eval/{run}/evaluation.json").read_text())
        # Busca en todos los experimentos: m1b-i1-seed0/1 quedaron en «Default» por una carrera al crear
        # warehouse-m1b (corregido en pipelines/tracking.py::experiment_id); se registra dónde está de verdad.
        experiments = {e.experiment_id: e.name for e in client.search_experiments()}
        found = client.search_runs(list(experiments), filter_string=f"tags.mlflow.runName = '{run}'")
        assert len(found) == 1, (run, len(found))
        mlrun = found[0]
        mlflow_experiment = experiments[mlrun.info.experiment_id]
        version = meta["environment_version"]
        sheet = version.replace("warehouse-v", "0.") + ".0"
        config_uri = f"configs/experiments/{d['config']}.yaml"
        m = dict(template)
        m.update(
            run_id=run, level_id=level, environment_version=version, git_commit=meta["git_revision"],
            config_sha256=sha256(config_uri), model_uri=f"models/{run}/model.zip",
            model_sha256=sha256(f"models/{run}/model.zip"), runtime_ref=f"env/{version}",
            evaluation_suite_id=f"suite-{level}-v1", seed=meta["seed"],
            parent_run_id=Path(meta["parent_model"]).parts[1] if meta.get("parent_model") else None,
            estado=d["estado"], created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            budget_steps=meta["effective_timesteps"], budget_minutes=round(meta["duration_seconds"] / 60, 2),
            mlflow_run_id=mlrun.info.run_id, mlflow_experiment=mlflow_experiment, config_uri=config_uri,
            obs_spec=template["obs_spec"].replace("v5", version.split("-")[-1]),
            action_spec=template["action_spec"].replace("v5", version.split("-")[-1]),
            rules_ref=f"docs/ambiente-v{sheet[:-2]}.md",
            layout_path=meta.get("layout_path"), layout_sha256=meta["layout_sha256"],
            results_uri=f"docs/resultados/eval/{run}/evaluation.json",
            training_metadata_uri=f"docs/resultados/training/{run}/metadata.json",
            git_dirty_note=(f"git_dirty figura true solo por carpetas de salida sin versionar de runs hermanos lanzados en paralelo; "
                            f"ningún archivo versionado cambió (commit {meta['git_revision'][:7]})" if meta["git_dirty"]
                            else f"git_dirty figura false; commit {meta['git_revision'][:7]}"),
            reward=meta["rewards"], reward_overrides=meta.get("reward_overrides") or {},
            stagnation_window=meta.get("stagnation_window"),
            decision=d["estado"], decision_reason=d["reason"])
        e = dict(template["evaluation"])
        e.update(suite=f"suite-{level}-v1",
                 scenario=("mapa con muro layout_v0.4" if "0.4" in str(meta.get("layout_path")) else "mapa abierto layout_v0.5"))
        e["policies"] = {p["policy"]: {k: p[k] for k in template["evaluation"]["policies"]["ppo"] if k in p} for p in ev["summary"]}
        m["evaluation"] = e
        validate(m, schema)
        out = Path(f"manifests/{run}.json")
        out.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
        client.set_tag(mlrun.info.run_id, "estado", d["estado"])
        print(run, d["estado"], version, m["budget_steps"], m["budget_minutes"], "min", "->", out)
    if any(json.loads(Path(f"docs/resultados/training/{r}/metadata.json").read_text())["environment_version"] != ENV_VERSION
           for r in decisions):
        print("aviso: algún run usó otra versión del ambiente que la actual", ENV_VERSION)


if __name__ == "__main__":
    main(sys.argv[1])
