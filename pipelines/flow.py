"""Flujo de Prefect (R3): de la configuración al modelo servido, con evidencia por etapa.

Etapas (secuencia mínima del curso):
  1 validar            config, rutas, esquema de manifiestos, catálogo al día y compatibilidad del ambiente
  2 probar             pruebas de reglas, observación, acciones y terminaciones (subconjunto rápido o todas)
  3 entrenar_o_cargar  cargar: manifiesto → dvc pull si falta → SHA-256; entrenar: train_from_config
  4 evaluar            suites fijas (configs/suites/) para el modelo y para el recomendado vigente del nivel
  5 registrar          MLflow (MLFLOW_TRACKING_URI): run del experimento `warehouse-pipeline` con evaluaciones,
                       modelo y procedencia, y versión del modelo `warehouse-<nivel>` (una por SHA-256)
  6 decidir            configs/criterios.yaml frente al recomendado vigente → recomendado (vigente) | candidato | rechazado
  7 publicar_catalogo  manifests/catalog.json (pipelines.registry) + alias recomendado/anterior en MLflow
  8 verificar_servido  GET <api_url>/version == modelo de producción del catálogo; sin api_url → pendiente

Cada etapa escribe `docs/resultados/flujo/<ejecución>/NN-<etapa>.json` (estado, tiempos, entradas, salidas).
Reejecutar reutiliza: evaluaciones por (modelo, suite), run y versión de MLflow por SHA-256, catálogo por
contenido. Nada se sobrescribe: un run ya entrenado se reutiliza y una versión nueva se pide con --sufijo.
El flujo NO promueve: una promoción o un rollback es una decisión explícita (pipelines.registry).

Uso:
  python -m pipelines.flow ejecutar --run-id m1b-i1-seed1-best --suite suite-m1-v1 --suite suite-m1b-v1
  python -m pipelines.flow ejecutar --config configs/experiments/m1_c3_largo_seed0.yaml --modo entrenar \
      --timesteps 8192                                  # prueba de humo: run nuevo m1-c3-humo8192-seed0
  python -m pipelines.flow rollback --ranura produccion --motivo "..." [--api-url https://...]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE

from pipelines import registry
from pipelines.tracking import canonical_json, experiment_id, git_info, sha256_config, sha256_file

RAIZ = registry.RAIZ
FLUJO_ROOT = Path(os.environ.get("WAREHOUSE_FLUJO_DIR", "docs/resultados/flujo"))  # otra carpeta solo para pruebas
EXPERIMENTO_PIPELINE = "warehouse-pipeline"
# Subconjunto rápido de «probar»: reglas, observación, acciones y terminaciones del ambiente (test_env,
# test_lift), recompensa (test_reward_config), inventario y misiones, mapas, empaque, parada de entrenamiento y
# registro. Quedan fuera las que entrenan (bc, incident, compare, tracking) y el adaptador viejo de Vercel
# (viewer, cloud). `--pruebas completas` corre tests/ entero.
PRUEBAS_RAPIDAS = ("tests/test_env.py", "tests/test_lift.py", "tests/test_reward_config.py",
                   "tests/test_inventory_missions.py", "tests/test_layouts.py", "tests/test_layout_perf.py",
                   "tests/test_packing.py", "tests/test_stagnation.py", "tests/test_registry.py")


class FlujoError(RuntimeError):
    """Una etapa no puede continuar (la evidencia de la etapa queda con estado `fallido`)."""


# --- Evidencia por etapa ---------------------------------------------------------------------------

class Evidencia:
    """Carpeta de una ejecución del flujo; cada etapa deja un JSON con su estado aunque falle."""

    def __init__(self, nombre: str):
        sello = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
        self.dir = RAIZ / FLUJO_ROOT / f"{sello}-{nombre}"
        self.dir.mkdir(parents=True, exist_ok=False)
        self.etapas: list[dict] = []

    def correr(self, numero: int, etapa: str, entradas: dict, fn):
        registro = {"etapa": etapa, "numero": numero, "inicio": _ahora(), "entradas": entradas}
        inicio = time.perf_counter()
        path = self.dir / f"{numero:02d}-{etapa}.json"
        try:
            salidas = fn()
        except Exception as exc:
            registro.update(estado="fallido", error=f"{type(exc).__name__}: {exc}"[:2000])
            raise
        else:
            registro.update(estado=salidas.pop("_estado", "ok"), salidas=salidas)
            return salidas
        finally:
            registro.update(fin=_ahora(), duracion_s=round(time.perf_counter() - inicio, 3))
            path.write_text(json.dumps(registro, indent=2, ensure_ascii=False, default=str) + "\n")
            self.etapas.append({k: registro[k] for k in ("numero", "etapa", "estado", "duracion_s")})

    def rel(self, path: Path) -> str:
        return _rel(path)


def _rel(path) -> str:
    path = Path(path).resolve()
    return str(path.relative_to(RAIZ)) if path.is_relative_to(RAIZ) else str(path)


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uri_sin_credenciales(uri: str) -> str:
    partes = urlsplit(uri)
    return partes._replace(netloc=partes.hostname or "").geturl() if partes.username or partes.password else uri


def _leer_yaml(path) -> dict:
    import yaml

    return yaml.safe_load((RAIZ / path).read_text())


def _suite(suite_id: str) -> dict:
    path = RAIZ / "configs/suites" / f"{suite_id}.yaml"
    if suite_id.startswith("test-final"):
        raise FlujoError("El flujo nunca usa una suite test-final (reservada; requiere pre-registro)")
    if not path.is_file():
        raise FlujoError(f"No existe la suite {path.relative_to(RAIZ)}")
    suite = _leer_yaml(path.relative_to(RAIZ))
    if suite.get("id") != suite_id:
        raise FlujoError(f"{path.name}: id '{suite.get('id')}' no coincide con el nombre del archivo")
    escenario = suite.get("escenario", "abierto")
    if escenario not in ("abierto", "bloqueado"):
        raise FlujoError(f"{suite_id}: escenario '{escenario}' desconocido")
    inicio, fin = suite["semillas_rango"]
    if fin - inicio + 1 != suite["episodios"]:
        raise FlujoError(f"{suite_id}: semillas_rango no cubre {suite['episodios']} episodios")
    return {**suite, "escenario": escenario}


# --- 1. validar ------------------------------------------------------------------------------------

def _validar(config_path: str | None, run_id: str | None, modo: str, suites: list[str] | None,
             sufijo: str | None, timesteps: int | None) -> dict:
    from envs import ENV_VERSION
    from pipelines.train import load_config, run_name_for

    manifest = None
    if modo == "cargar":
        if not run_id:
            raise FlujoError("modo cargar necesita --run-id (un manifiesto de manifests/)")
        manifest = registry.cargar_manifiesto(run_id)
        if manifest["environment_version"] != ENV_VERSION:
            raise FlujoError(f"{run_id} es de {manifest['environment_version']}; este código es {ENV_VERSION}. "
                             f"Evalúalo desde su runtime_ref ({manifest['runtime_ref']})")
        config_manifest = manifest.get("config_uri")
        if config_path and config_manifest and Path(config_path) != Path(config_manifest):
            raise FlujoError(f"--config {config_path} no es el config del manifiesto ({config_manifest})")
        config_path = config_path or config_manifest
    elif modo != "entrenar":
        raise FlujoError("modo debe ser cargar o entrenar")
    if not config_path or not (RAIZ / config_path).is_file():
        raise FlujoError(f"No existe el config {config_path}")
    config = load_config(RAIZ / config_path)  # claves, versión del ambiente, recompensa, nivel, parada
    nivel = _leer_yaml("configs/niveles.yaml")[config["nivel"]]
    layout = config.get("layout")
    if layout and not (RAIZ / layout).is_file():
        raise FlujoError(f"No existe el mapa {layout}")
    suites = suites or [config.get("evaluacion", {}).get("final") or (manifest or {}).get("evaluation_suite_id")]
    suites_info = {s: _suite(s) for s in suites if s}
    if not suites_info:
        raise FlujoError("No hay suite de evaluación (config evaluacion.final o --suite)")
    # m1b (incidente) se evalúa también en la suite de m1 para medir el olvido (configs/niveles.yaml)
    niveles_suite = {config["nivel"], "m1"} if config["nivel"] == "m1b" else {config["nivel"]}
    for suite_id, suite in suites_info.items():
        if suite.get("nivel") not in niveles_suite:
            raise FlujoError(f"{suite_id} es del nivel {suite.get('nivel')}, el config es {config['nivel']}")

    hash_config = {"canonico": sha256_config(config), "archivo": sha256_file(RAIZ / config_path)}
    if manifest:
        formato = next((k for k, v in hash_config.items() if v == manifest["config_sha256"]), None)
        if formato is None:
            raise FlujoError(f"El config {config_path} cambió desde el run: su hash no coincide con el manifiesto")
        hash_config["manifiesto_usa"] = formato
    run_name = run_id if manifest else run_name_for(config)
    if modo == "entrenar":
        sufijo = sufijo or (f"humo{timesteps}" if timesteps and timesteps < config["presupuesto_pasos"] else None)
        if sufijo:
            run_name = run_name_for({**config, "id": f"{config['id']}-{sufijo}"})

    manifiestos, excluidos = registry.listar_manifiestos()
    publicado = json.loads((RAIZ / "manifests/catalog.json").read_text())
    catalogo_al_dia = publicado["contenido_sha256"] == registry.construir_catalogo()["contenido_sha256"]
    if not catalogo_al_dia:
        raise FlujoError("manifests/catalog.json no está al día: python -m pipelines.registry catalogo")
    tracking = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    return {"modo": modo, "run_id": run_name, "config_path": str(config_path), "config": config,
            "nivel": config["nivel"], "orders": nivel["orders"], "layout": layout,
            "suites": suites_info, "sufijo": sufijo, "config_sha256": hash_config,
            "environment_version": ENV_VERSION, "manifiestos_validos": len(manifiestos),
            "manifiestos_excluidos": [e["archivo"] for e in excluidos], "catalogo_al_dia": catalogo_al_dia,
            "mlflow_tracking_uri": _uri_sin_credenciales(tracking), "git": git_info()}


@task(name="1-validar", cache_policy=NO_CACHE)
def validar(ev: Evidencia, config_path, run_id, modo, suites, sufijo, timesteps) -> dict:
    entradas = {"config": config_path, "run_id": run_id, "modo": modo, "suites": suites,
                "sufijo": sufijo, "timesteps": timesteps}
    return ev.correr(1, "validar", entradas,
                     lambda: _validar(config_path, run_id, modo, suites, sufijo, timesteps))


# --- 2. probar -------------------------------------------------------------------------------------

@task(name="2-probar", cache_policy=NO_CACHE)
def probar(ev: Evidencia, pruebas: str) -> dict:
    archivos = list(PRUEBAS_RAPIDAS) if pruebas == "rapidas" else ["tests"]
    junit = ev.dir / "02-probar.junit.xml"

    def correr():
        if pruebas not in ("rapidas", "completas"):
            raise FlujoError("pruebas debe ser rapidas o completas")
        cmd = [sys.executable, "-m", "pytest", *archivos, "-q", "-n", "6", "--dist", "loadfile",
               "-p", "no:cacheprovider", f"--junitxml={junit}"]
        proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True,
                              env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1"})
        resumen = (proc.stdout.strip().splitlines() or [""])[-1]
        (ev.dir / "02-probar.log").write_text(proc.stdout + proc.stderr)
        if proc.returncode != 0:
            raise FlujoError(f"pytest terminó con código {proc.returncode}: {resumen}")
        return {"conjunto": pruebas, "archivos": archivos, "resumen": resumen,
                "junit": ev.rel(junit), "log": ev.rel(ev.dir / "02-probar.log")}

    return ev.correr(2, "probar", {"conjunto": pruebas, "archivos": archivos}, correr)


# --- 3. entrenar_o_cargar --------------------------------------------------------------------------

def _config_derivado(ev: Evidencia, ctx: dict) -> Path:
    """Config de una versión nueva explícita (--sufijo o prueba de humo): mismo YAML con otro id."""
    import yaml

    config = {**ctx["config"], "id": f"{ctx['config']['id']}-{ctx['sufijo']}"}
    path = ev.dir / f"{ctx['run_id']}.yaml"
    path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    return path


def _entrenar_o_cargar(ev: Evidencia, ctx: dict, timesteps: int | None) -> dict:
    run_id = ctx["run_id"]
    if ctx["modo"] == "cargar":
        verificado = registry.verificar_modelo(run_id, descargar=True)
        if not verificado["ok"]:
            raise FlujoError(f"{run_id}: {verificado.get('error')}")
        return {"_estado": "reutilizado", "origen": "manifiesto", "model_path": verificado["model_uri"],
                "model_sha256": verificado["real"], "descargado_con_dvc": verificado["descargado"],
                "mlflow_run_id_entrenamiento": None}
    modelo = RAIZ / "models" / run_id / "model.zip"
    carpeta_run = RAIZ / "docs/resultados/training" / run_id
    if modelo.is_file():  # ya entrenado: se reutiliza, nunca se reentrena encima
        path_manifiesto = RAIZ / "manifests" / f"{run_id}.json"
        sha = sha256_file(modelo)
        if path_manifiesto.is_file() and registry.cargar_manifiesto(run_id)["model_sha256"] != sha:
            raise FlujoError(f"{run_id}: el modelo en disco no coincide con su manifiesto")
        return {"_estado": "reutilizado", "origen": "run existente", "model_path": str(modelo.relative_to(RAIZ)),
                "model_sha256": sha, "mlflow_run_id_entrenamiento": None}
    if carpeta_run.exists() or (RAIZ / "models" / run_id).exists():
        raise FlujoError(f"{run_id} ya existe sin model.zip (fallido o interrumpido): usa --sufijo para una versión nueva")
    from pipelines.train import train_from_config

    config_path = _config_derivado(ev, ctx) if ctx["sufijo"] else RAIZ / ctx["config_path"]
    meta = train_from_config(config_path, timesteps=timesteps)
    modelo = Path(meta["model_path"])
    return {"origen": "entrenado", "config_usado": ev.rel(config_path), "model_path": str(modelo),
            "model_sha256": sha256_file(RAIZ / modelo), "pasos_reales": meta["effective_timesteps"],
            "minutos": round(meta["duration_seconds"] / 60, 2),
            "mlflow_run_id_entrenamiento": meta["mlflow_run_id"], "metadata": meta}


@task(name="3-entrenar-o-cargar", cache_policy=NO_CACHE)
def entrenar_o_cargar(ev: Evidencia, ctx: dict, timesteps: int | None) -> dict:
    entradas = {"modo": ctx["modo"], "run_id": ctx["run_id"], "timesteps": timesteps}
    return ev.correr(3, "entrenar_o_cargar", entradas, lambda: _entrenar_o_cargar(ev, ctx, timesteps))


# --- 4. evaluar ------------------------------------------------------------------------------------

def _metricas(path: Path) -> dict:
    data = json.loads(path.read_text())
    filas = [s for s in data["summary"] if s["policy"] == "ppo"]
    if not data["completed"] or len(filas) != 1:
        raise FlujoError(f"{path}: evaluación incompleta o ambigua ({data.get('errors')})")
    f = filas[0]
    return {"episodios": f["episodes"], "exito": f["success_rate"], "choques": f["mean_collisions"],
            "invalidas": f["mean_invalid_interactions"], "entregas": f["mean_deliveries"],
            "pasos": f["mean_steps"], "end_reasons": f["end_reasons"]}


def _evaluar_modelo(run_id: str, model_path: str, model_sha: str, suite: dict, *, orders: int,
                    layout: str | None, recompensa: dict | None) -> dict:
    """Evalúa (o reutiliza) un modelo en una suite. Carpeta = (run, suite, sha): nunca se sobrescribe."""
    from pipelines.evaluate import evaluate

    salida = RAIZ / FLUJO_ROOT / "eval" / run_id / f"{suite['id']}-{model_sha[:12]}"
    archivo = salida / "evaluation.json"
    seeds = list(range(suite["semillas_rango"][0], suite["semillas_rango"][1] + 1))
    if archivo.is_file():
        previo = json.loads(archivo.read_text())["configuration"]
        if previo.get("model_sha256") != model_sha or previo.get("seeds") != seeds:
            raise FlujoError(f"{archivo} existe con otro modelo o semillas: revísalo, no se sobrescribe")
        reutilizada = True
    else:
        evaluate(policies=("ppo",), orders=orders, episodes=suite["episodios"], seed_start=seeds[0],
                 scenarios=(suite["escenario"] == "bloqueado",), model_path=RAIZ / model_path,
                 layout_path=layout, output_dir=salida, reward_overrides=recompensa)
        reutilizada = False
    return {"run_id": run_id, "suite": suite["id"], "escenario": suite["escenario"],
            "evaluation_json": _rel(archivo), "evaluation_sha256": sha256_file(archivo),
            "reutilizada": reutilizada, "metricas": _metricas(archivo)}


def _evaluar(ctx: dict, modelo: dict) -> dict:
    aliases = registry.cargar_aliases()
    referencia_id = aliases["ranuras"].get(ctx["nivel"], {}).get("actual")
    referencia = None
    if referencia_id and referencia_id != ctx["run_id"]:
        manifest_ref = registry.cargar_manifiesto(referencia_id)
        if manifest_ref.get("layout_path") and ctx["layout"] and manifest_ref["layout_path"] != ctx["layout"]:
            raise FlujoError(f"El recomendado {referencia_id} usa otro mapa ({manifest_ref['layout_path']})")
        verificado = registry.verificar_modelo(referencia_id, descargar=True)
        if not verificado["ok"]:
            raise FlujoError(f"Referencia {referencia_id}: {verificado.get('error')}")
        referencia = {"run_id": referencia_id, "model_path": manifest_ref["model_uri"],
                      "model_sha256": verificado["real"], "recompensa": manifest_ref.get("reward_overrides"),
                      "layout": manifest_ref.get("layout_path")}
    comun = {"orders": ctx["orders"]}
    resultados = {}
    for suite_id, suite in ctx["suites"].items():
        resultados[suite_id] = {
            "modelo": _evaluar_modelo(ctx["run_id"], modelo["model_path"], modelo["model_sha256"], suite,
                                      layout=ctx["layout"], recompensa=ctx["config"].get("recompensa"), **comun),
            "referencia": (_evaluar_modelo(referencia["run_id"], referencia["model_path"],
                                           referencia["model_sha256"], suite, layout=referencia["layout"],
                                           recompensa=referencia["recompensa"], **comun) if referencia else None),
        }
    todas = [r for s in resultados.values() for r in s.values() if r]
    return {"_estado": "reutilizado" if all(r["reutilizada"] for r in todas) else "ok",
            "referencia": referencia_id if referencia else None, "por_suite": resultados}


@task(name="4-evaluar", cache_policy=NO_CACHE)
def evaluar(ev: Evidencia, ctx: dict, modelo: dict) -> dict:
    entradas = {"run_id": ctx["run_id"], "model_sha256": modelo["model_sha256"], "suites": list(ctx["suites"])}
    return ev.correr(4, "evaluar", entradas, lambda: _evaluar(ctx, modelo))


# --- 5. registrar ----------------------------------------------------------------------------------

def _run_origen(client, ctx: dict, modelo: dict) -> str | None:
    """Run de MLflow del entrenamiento: el recién creado, o el migrado (tag origen_run_id) / por nombre."""
    if modelo.get("mlflow_run_id_entrenamiento"):
        return modelo["mlflow_run_id_entrenamiento"]
    exp = client.get_experiment_by_name(f"warehouse-{ctx['nivel']}")
    if exp is None:
        return None
    manifest_path = RAIZ / "manifests" / f"{ctx['run_id']}.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    filtros = []
    if manifest.get("mlflow_run_id"):
        filtros += [f"tags.origen_run_id = '{manifest['mlflow_run_id']}'", f"attributes.run_id = '{manifest['mlflow_run_id']}'"]
    entrenamiento = Path(manifest.get("training_metadata_uri", f"x/{ctx['run_id']}/m")).parent.name
    filtros.append(f"attributes.run_name = '{entrenamiento}'")
    for filtro in filtros:
        encontrados = client.search_runs([exp.experiment_id], filter_string=filtro, max_results=2)
        if len(encontrados) == 1:
            return encontrados[0].info.run_id
    return None


def _registrar(ctx: dict, modelo: dict, evaluacion: dict) -> dict:
    import mlflow
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    client = MlflowClient()
    evals = {s: r["modelo"] for s, r in evaluacion["por_suite"].items()}
    clave = sha256(canonical_json({"model_sha256": modelo["model_sha256"],
                                   "evaluaciones": {s: e["evaluation_sha256"] for s, e in sorted(evals.items())}}
                                  ).encode()).hexdigest()
    exp_id = experiment_id(EXPERIMENTO_PIPELINE)
    previos = client.search_runs([exp_id], filter_string=f"tags.clave_registro = '{clave}'", max_results=1)
    origen = _run_origen(client, ctx, modelo)
    if previos:
        run_id_mlflow, reutilizado = previos[0].info.run_id, True
    else:
        tags = {"run_id": ctx["run_id"], "nivel": ctx["nivel"], "tipo": "registro",
                "environment_version": ctx["environment_version"], "runtime_ref": f"env/{ctx['environment_version']}",
                "model_sha256": modelo["model_sha256"], "config_sha256": ctx["config_sha256"]["canonico"],
                "config_uri": ctx["config_path"], "origen_mlflow_run_id": origen or "no encontrado",
                "suites": ",".join(evals), "clave_registro": clave, **git_info()}
        with mlflow.start_run(experiment_id=exp_id, run_name=f"registro-{ctx['run_id']}", tags=tags) as run:
            for suite_id, e in evals.items():
                m = e["metricas"]
                mlflow.log_metrics({f"eval/{suite_id}/exito": m["exito"], f"eval/{suite_id}/choques": m["choques"],
                                    f"eval/{suite_id}/invalidas": m["invalidas"],
                                    f"eval/{suite_id}/entregas": m["entregas"], f"eval/{suite_id}/pasos": m["pasos"]})
                mlflow.log_artifact(str(RAIZ / e["evaluation_json"]), artifact_path=f"evaluacion/{suite_id}")
            mlflow.log_dict(ctx["config"], "config.json")
            mlflow.log_artifact(str(RAIZ / modelo["model_path"]), artifact_path="modelo")
            manifest = RAIZ / "manifests" / f"{ctx['run_id']}.json"
            if manifest.is_file():
                mlflow.log_artifact(str(manifest), artifact_path="manifiesto")
            run_id_mlflow, reutilizado = run.info.run_id, False
    version = _version_modelo(client, MlflowException, ctx, modelo, run_id_mlflow)
    return {"_estado": "reutilizado" if reutilizado and version["reutilizada"] else "ok",
            "mlflow_tracking_uri": _uri_sin_credenciales(mlflow.get_tracking_uri()),
            "experimento": EXPERIMENTO_PIPELINE, "mlflow_run_id": run_id_mlflow, "run_reutilizado": reutilizado,
            "clave_registro": clave, "origen_mlflow_run_id": origen, "modelo_registrado": version}


def _version_modelo(client, MlflowException, ctx: dict, modelo: dict, run_id_mlflow: str) -> dict:
    """Una versión de `warehouse-<nivel>` por SHA-256 del modelo; si ya existe, se reutiliza."""
    nombre = f"warehouse-{ctx['nivel']}"
    try:
        client.create_registered_model(nombre, description=f"Modelos PPO del nivel {ctx['nivel']} (Warehouse Rush)")
    except MlflowException:
        pass  # ya existe
    for version in client.search_model_versions(f"name = '{nombre}'"):
        if version.tags.get("model_sha256") == modelo["model_sha256"]:
            return {"nombre": nombre, "version": version.version, "reutilizada": True}
    fuente = f"{client.get_run(run_id_mlflow).info.artifact_uri}/modelo"
    version = client.create_model_version(nombre, fuente, run_id=run_id_mlflow,
                                          tags={"model_sha256": modelo["model_sha256"], "run_id": ctx["run_id"],
                                                "environment_version": ctx["environment_version"]})
    return {"nombre": nombre, "version": version.version, "reutilizada": False}


@task(name="5-registrar", cache_policy=NO_CACHE, retries=2, retry_delay_seconds=10)
def registrar(ev: Evidencia, ctx: dict, modelo: dict, evaluacion: dict) -> dict:
    entradas = {"run_id": ctx["run_id"], "model_sha256": modelo["model_sha256"]}
    return ev.correr(5, "registrar", entradas, lambda: _registrar(ctx, modelo, evaluacion))


# --- 6. decidir ------------------------------------------------------------------------------------

def _decidir(ctx: dict, modelo: dict, evaluacion: dict, registro: dict) -> dict:
    criterios = _leer_yaml("configs/criterios.yaml")
    regla = criterios["adoptar_si"]
    manifest_path = RAIZ / "manifests" / f"{ctx['run_id']}.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else None
    if evaluacion["referencia"] is None:
        vigente = registry.cargar_aliases()["ranuras"].get(ctx["nivel"], {}).get("actual") == ctx["run_id"]
        estado = "recomendado" if vigente else "candidato"
        motivo = ("es el recomendado vigente del nivel; no se compara consigo mismo" if vigente
                  else "el nivel no tiene recomendado vigente con el que comparar")
        comparacion = {}
    else:
        comparacion = {}
        for suite_id, r in evaluacion["por_suite"].items():
            c, b = r["modelo"]["metricas"], r["referencia"]["metricas"]
            mejora = round((c["exito"] - b["exito"]) * 100, 4)
            limite = b["choques"] * (1 + regla["aumento_choques_max_pct"] / 100)
            comparacion[suite_id] = {"exito": c["exito"], "exito_referencia": b["exito"], "mejora_pp": mejora,
                                     "choques": c["choques"], "choques_referencia": b["choques"],
                                     "cumple_exito": mejora >= regla["mejora_exito_pp_min"],
                                     "cumple_choques": c["choques"] <= limite + 1e-9}
        cumple = all(v["cumple_exito"] and v["cumple_choques"] for v in comparacion.values())
        estado = "candidato" if cumple else criterios.get("si_no_cumple", "rechazado")
        motivo = (f"configs/criterios.yaml v{criterios['version']} frente a {evaluacion['referencia']}: "
                  + ("cumple en todas las suites; apto para promoción explícita (pipelines.registry promover)"
                     if cumple else "no cumple en al menos una suite"))
    salida = {"estado_propuesto": estado, "motivo": motivo, "criterios_version": criterios["version"],
              "referencia": evaluacion["referencia"], "comparacion": comparacion, "manifiesto_creado": None}
    if manifest is None:  # run nuevo de este flujo: su manifiesto registra la decisión (y luego es inmutable)
        salida["manifiesto_creado"] = _crear_manifiesto(ctx, modelo, evaluacion, registro, estado, motivo)
        if modelo.get("mlflow_run_id_entrenamiento"):
            from mlflow.tracking import MlflowClient

            MlflowClient().set_tag(modelo["mlflow_run_id_entrenamiento"], "estado", estado)
    else:
        salida["estado_manifiesto"] = manifest.get("estado")
        salida["coincide_con_manifiesto"] = manifest.get("estado") == estado
        # el manifiesto es inmutable: una discrepancia queda en la evidencia, no se corrige aquí
    return salida


def _crear_manifiesto(ctx, modelo, evaluacion, registro, estado, motivo) -> str:
    meta = modelo.get("metadata") or {}
    primera = next(iter(evaluacion["por_suite"]))
    manifest = {
        "schema_version": 1, "run_id": ctx["run_id"], "level_id": ctx["nivel"],
        "environment_version": ctx["environment_version"], "git_commit": meta.get("git_revision") or git_info()["git_commit"],
        "config_sha256": sha256_config(_leer_yaml(modelo.get("config_usado") or ctx["config_path"])),
        "model_uri": modelo["model_path"], "model_sha256": modelo["model_sha256"], "normalization_uri": None,
        "runtime_ref": f"env/{ctx['environment_version']}", "evaluation_suite_id": primera,
        "seed": ctx["config"]["seed"], "parent_run_id": ctx["config"].get("parent_run_id"),
        "estado": estado, "created_at": _ahora(), "author": registry._autor(None), "algorithm": meta.get("algorithm"),
        "policy": meta.get("policy"), "budget_steps": meta.get("effective_timesteps"),
        "budget_minutes": round(meta["duration_seconds"] / 60, 2) if meta.get("duration_seconds") else None,
        "mlflow_run_id": modelo.get("mlflow_run_id_entrenamiento"), "mlflow_experiment": f"warehouse-{ctx['nivel']}",
        "mlflow_registro_run_id": registro["mlflow_run_id"], "modelo_registrado": registro["modelo_registrado"],
        "config_uri": modelo.get("config_usado") or ctx["config_path"], "layout_path": ctx["layout"],
        "git_dirty": meta.get("git_dirty"), "reward_overrides": ctx["config"].get("recompensa") or {},
        "results_uri": evaluacion["por_suite"][primera]["modelo"]["evaluation_json"],
        "evaluaciones": {s: r["modelo"]["metricas"] for s, r in evaluacion["por_suite"].items()},
        "decision": estado, "decision_reason": motivo,
        "weights_storage": "local hasta `dvc add models/<run>` + commit del .dvc + `dvc push`",
    }
    errores = registry.errores_manifiesto(manifest)
    if errores:
        raise FlujoError(f"Manifiesto nuevo inválido: {errores}")
    path = RAIZ / "manifests" / f"{ctx['run_id']}.json"
    with path.open("x") as handle:  # «x»: falla si ya existe, nunca sobrescribe
        handle.write(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return str(path.relative_to(RAIZ))


@task(name="6-decidir", cache_policy=NO_CACHE)
def decidir(ev: Evidencia, ctx: dict, modelo: dict, evaluacion: dict, registro: dict) -> dict:
    entradas = {"run_id": ctx["run_id"], "referencia": evaluacion["referencia"], "criterios": "configs/criterios.yaml"}
    return ev.correr(6, "decidir", entradas, lambda: _decidir(ctx, modelo, evaluacion, registro))


# --- 7. publicar_catalogo --------------------------------------------------------------------------

def _sincronizar_alias_mlflow() -> dict:
    """Alias `recomendado`/`anterior` de cada `warehouse-<nivel>` según aliases.json (mejor esfuerzo:
    si el modelo de la ranura no tiene versión registrada aún, se informa y no se toca).

    La versión se identifica por el tag `model_sha256` (el del manifiesto), no por el nombre del run: las
    versiones migradas a DagsHub llevan el tag `modelo` y las del flujo `run_id`, pero ambas llevan el SHA-256.
    Solo se escribe un alias si cambia."""
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    resultado = {}
    for ranura, valor in registry.cargar_aliases()["ranuras"].items():
        if ranura == registry.PRODUCCION:
            continue
        nombre = f"warehouse-{ranura}"
        try:
            registradas = client.search_model_versions(f"name = '{nombre}'")
            # search_model_versions no trae los alias (MLflow 3.18); el modelo registrado sí: {alias: versión}
            vigentes = {a: str(v) for a, v in client.get_registered_model(nombre).aliases.items()} if registradas else {}
        except Exception as exc:
            resultado[nombre] = f"sin acceso: {type(exc).__name__}"
            continue
        por_sha = {v.tags.get("model_sha256"): v for v in registradas if v.tags.get("model_sha256")}
        resultado[nombre] = {}
        for alias, run in (("recomendado", valor["actual"]), ("anterior", valor["anterior"])):
            version = por_sha.get(registry.cargar_manifiesto(run)["model_sha256"]) if run else None
            if version is None:
                resultado[nombre][alias] = {"run_id": run, "version": None, "accion": "sin versión registrada"}
                continue
            accion = "sin cambio" if vigentes.get(alias) == str(version.version) else "asignado"
            if accion == "asignado":
                client.set_registered_model_alias(nombre, alias, version.version)
            resultado[nombre][alias] = {"run_id": run, "version": version.version, "accion": accion}
    return resultado


@task(name="7-publicar-catalogo", cache_policy=NO_CACHE)
def publicar_catalogo(ev: Evidencia) -> dict:
    def correr():
        catalogo = registry.publicar_catalogo()
        try:
            alias = _sincronizar_alias_mlflow()
        except Exception as exc:
            alias = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        return {"_estado": "reutilizado" if catalogo["reutilizado"] else "ok",
                "catalogo": "manifests/catalog.json", "contenido_sha256": catalogo["contenido_sha256"],
                "aliases_version": catalogo["aliases_version"], "produccion": catalogo["produccion"],
                "niveles": catalogo["niveles"], "alias_mlflow": alias}

    return ev.correr(7, "publicar_catalogo", {}, correr)


# --- 8. verificar_servido --------------------------------------------------------------------------

def _verificar_servido(api_url: str | None, intentos: int = 3, espera_s: float = 5.0) -> dict:
    servido = registry.modelo_servido()
    esperado = {"run_id": servido["run_id"], "model_sha256": servido["model_sha256"],
                "environment_version": servido["environment_version"]}
    if not api_url:
        return {"_estado": "pendiente", "motivo": "sin --api-url (la API aún no está desplegada)", "esperado": esperado}
    import httpx

    url = f"{api_url.rstrip('/')}/version"
    ultimo = None
    for intento in range(1, intentos + 1):
        try:
            respuesta = httpx.get(url, timeout=15)
            respuesta.raise_for_status()
            ultimo = respuesta.json()
            servida = {k: ultimo.get(k) for k in esperado}
            if servida == esperado:
                return {"url": url, "intento": intento, "esperado": esperado, "servido": ultimo, "coincide": True}
        except Exception as exc:
            ultimo = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        if intento < intentos:
            time.sleep(espera_s)
    raise FlujoError(f"La API no sirve el modelo de producción del catálogo: esperado {esperado}, servido {ultimo}")


@task(name="8-verificar-servido", cache_policy=NO_CACHE)
def verificar_servido(ev: Evidencia, api_url: str | None, numero: int = 8) -> dict:
    return ev.correr(numero, "verificar_servido", {"api_url": api_url}, lambda: _verificar_servido(api_url))


# --- Flujos ----------------------------------------------------------------------------------------

def _preparar() -> None:
    """Rutas relativas de train/evaluate cuelgan de la raíz del repo; .env aporta MLflow (sin pisar el entorno)."""
    from dotenv import load_dotenv

    os.chdir(RAIZ)
    load_dotenv(RAIZ / ".env", override=False)


def _cerrar(ev: Evidencia, extra: dict) -> dict:
    resumen = {"carpeta": ev.rel(ev.dir), "etapas": ev.etapas, **extra, "fin": _ahora()}
    try:
        from prefect.runtime import flow_run

        resumen["prefect_flow_run_id"] = str(flow_run.id)
    except Exception:
        pass
    (ev.dir / "resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False, default=str) + "\n")
    return resumen


@flow(name="warehouse-pipeline", log_prints=True)
def warehouse_pipeline(config: str | None = None, run_id: str | None = None, modo: str = "cargar",
                       suites: list[str] | None = None, timesteps: int | None = None, sufijo: str | None = None,
                       pruebas: str = "rapidas", api_url: str | None = None) -> dict:
    _preparar()
    log = get_run_logger()
    ev = Evidencia(run_id or Path(config or "sin-config").stem)
    try:
        ctx = validar(ev, config, run_id, modo, suites, sufijo, timesteps)
        log.info("1 validar: %s (%s), suites %s", ctx["run_id"], ctx["nivel"], list(ctx["suites"]))
        p = probar(ev, pruebas)
        log.info("2 probar: %s", p["resumen"])
        modelo = entrenar_o_cargar(ev, ctx, timesteps)
        log.info("3 modelo: %s sha256 %s… (%s)", modelo["model_path"], modelo["model_sha256"][:12], modelo["origen"])
        evaluacion = evaluar(ev, ctx, modelo)
        for suite_id, r in evaluacion["por_suite"].items():
            ref = r["referencia"]["metricas"]["exito"] if r["referencia"] else None
            log.info("4 %s: éxito %.0f%% (referencia %s)", suite_id, 100 * r["modelo"]["metricas"]["exito"],
                     f"{100 * ref:.0f}%" if ref is not None else "-")
        registro = registrar(ev, ctx, modelo, evaluacion)
        log.info("5 MLflow: run %s, %s v%s", registro["mlflow_run_id"], registro["modelo_registrado"]["nombre"],
                 registro["modelo_registrado"]["version"])
        decision = decidir(ev, ctx, modelo, evaluacion, registro)
        log.info("6 decisión: %s (%s)", decision["estado_propuesto"], decision["motivo"])
        catalogo = publicar_catalogo(ev)
        log.info("7 catálogo %s…, producción %s", catalogo["contenido_sha256"][:12], catalogo["produccion"]["actual"])
        servido = verificar_servido(ev, api_url)
        log.info("8 servido: %s", servido.get("coincide", servido.get("motivo")))
    finally:
        resumen = _cerrar(ev, {"flujo": "warehouse-pipeline", "run_id": run_id or config})
    return resumen


@flow(name="warehouse-rollback", log_prints=True)
def warehouse_rollback(ranura: str = registry.PRODUCCION, motivo: str = "", api_url: str | None = None,
                       autor: str | None = None) -> dict:
    """Vuelve la ranura a su versión anterior, publica el catálogo y verifica lo servido."""
    _preparar()
    ev = Evidencia(f"rollback-{ranura}")
    try:
        antes = registry.cargar_aliases()["ranuras"].get(ranura)
        ev.correr(1, "rollback", {"ranura": ranura, "motivo": motivo, "antes": antes},
                  lambda: {"despues": registry.rollback(ranura, motivo=motivo, autor=autor)["ranuras"][ranura]})
        publicar_catalogo(ev)
        verificar_servido(ev, api_url, numero=3)
    finally:
        resumen = _cerrar(ev, {"flujo": "warehouse-rollback", "ranura": ranura})
    return resumen


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Flujo de Prefect de Warehouse Rush")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ejecutar", help="las 8 etapas para un modelo")
    p.add_argument("--config")
    p.add_argument("--run-id")
    p.add_argument("--modo", choices=("cargar", "entrenar"), default="cargar")
    p.add_argument("--suite", action="append", dest="suites")
    p.add_argument("--timesteps", type=int)
    p.add_argument("--sufijo", help="versión nueva explícita del run: <nivel>-<id>-<sufijo>-seed<semilla>")
    p.add_argument("--pruebas", choices=("rapidas", "completas"), default="rapidas")
    p.add_argument("--api-url")
    p = sub.add_parser("rollback", help="vuelve una ranura a su versión anterior")
    p.add_argument("--ranura", default=registry.PRODUCCION)
    p.add_argument("--motivo", required=True)
    p.add_argument("--api-url")
    p.add_argument("--autor")
    args = parser.parse_args(argv)
    if args.cmd == "ejecutar":
        resumen = warehouse_pipeline(config=args.config, run_id=args.run_id, modo=args.modo, suites=args.suites,
                                     timesteps=args.timesteps, sufijo=args.sufijo, pruebas=args.pruebas,
                                     api_url=args.api_url)
    else:
        resumen = warehouse_rollback(ranura=args.ranura, motivo=args.motivo, api_url=args.api_url, autor=args.autor)
    print(json.dumps(resumen, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
