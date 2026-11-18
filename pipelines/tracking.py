"""Trazabilidad mínima (R3 es dueño; R2 la usa): hashes, git y runs de MLflow.

Cada run registra params, tags (git_commit, environment_version, config_sha256, nivel,
hipótesis, parent_run_id, tipo, estado) y artefactos (config.json, modelo, métricas).
URI: variable MLFLOW_TRACKING_URI = servidor persistente del equipo (DagsHub, ver .env.example).
Sin ella el run falla en vez de quedar en un sqlite local que nadie más ve; para pruebas sueltas
MLFLOW_PERMITIR_LOCAL=1 usa sqlite:///mlflow.db (que NO va a Git).
"""

from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

ESTADOS = ("candidato", "recomendado", "rechazado", "fallido", "interrumpido")


def sha256_file(path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(config: dict) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_config(config: dict) -> str:
    """Hash sobre JSON canónico: el formato del YAML no cambia el hash."""
    return sha256(canonical_json(config).encode()).hexdigest()


def git_info() -> dict:
    def run(*args):
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()
    return {"git_commit": run("rev-parse", "HEAD"), "git_dirty": str(bool(run("status", "--porcelain"))).lower()}


def flatten(data: dict, prefix="") -> dict:
    out = {}
    for key, value in data.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, f"{name}."))
        else:
            out[name] = value
    return out


def experiment_id(name: str) -> str:
    """Id del experimento `name`, creándolo si falta. Varios entrenamientos lanzados a la vez pueden
    intentar crearlo al mismo tiempo; quien pierde la carrera relee el id en vez de caer en «Default»
    (pasó con m1b-i1-seed0/1, 2026-11-15)."""
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    found = client.get_experiment_by_name(name)
    if found is not None:
        return found.experiment_id
    try:
        return client.create_experiment(name)
    except Exception:
        found = client.get_experiment_by_name(name)
        if found is None:
            raise
        return found.experiment_id


def tracking_uri() -> str:
    """URI del servidor MLflow. Falla claro si falta, para que ningún entrenamiento quede solo en local."""
    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if uri:
        return uri
    if os.environ.get("MLFLOW_PERMITIR_LOCAL") == "1":
        return "sqlite:///mlflow.db"
    raise RuntimeError(
        "MLFLOW_TRACKING_URI no está definida: el run quedaría solo en este equipo. "
        "Carga las variables del servidor (`set -a; source .env; set +a`, ver .env.example) "
        "o, para una prueba local deliberada, exporta MLFLOW_PERMITIR_LOCAL=1.")


@contextmanager
def mlflow_run(*, experiment: str, run_name: str, config: dict, tags: dict):
    """Abre un run con params y tags; al salir marca estado y conserva el error si falla."""
    import mlflow

    mlflow.set_tracking_uri(tracking_uri())
    with mlflow.start_run(run_name=run_name, experiment_id=experiment_id(experiment)) as run:
        mlflow.log_params({k: str(v)[:500] for k, v in flatten(config).items()})
        mlflow.log_dict(config, "config.json")
        mlflow.set_tags({**git_info(), **{k: str(v) for k, v in tags.items()}})
        try:
            yield run
        except KeyboardInterrupt:
            mlflow.set_tags({"estado": "interrumpido", "sin_checkpoint": "true"})
            raise
        except Exception as exc:
            mlflow.set_tags({"estado": "fallido", "error": f"{type(exc).__name__}: {exc}"[:500],
                             "sin_checkpoint": "true"})
            raise
