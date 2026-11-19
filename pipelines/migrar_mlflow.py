"""Copia el historial MLflow local (sqlite:///mlflow.db + mlruns/) al servidor persistente.

Destino: MLFLOW_TRACKING_URI (+ MLFLOW_TRACKING_USERNAME/PASSWORD), p. ej. DagsHub.
Cada run copiado conserva nombre, params, tags, estado, tiempos, historial completo de
métricas y artefactos, y recibe el tag `origen_run_id` (id local). El servidor asigna ids
nuevos; el mapa viejo -> nuevo queda en docs/resultados/mlflow-migracion.json.

Idempotente: un run con `origen_run_id` y `migracion=completa` en el destino se salta;
uno a medias (sin `migracion=completa`) se borra y se vuelve a copiar.

Uso:
    set -a; source .env; set +a
    python -m pipelines.migrar_mlflow --solo <run_name>   # prueba con un run
    python -m pipelines.migrar_mlflow                     # todos
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mlflow.entities import Metric, Param, RunTag
from mlflow.tracking import MlflowClient

ORIGEN = "sqlite:///mlflow.db"
MAPA = Path("docs/resultados/mlflow-migracion.json")
# Runs que cayeron en `Default` por la carrera al crear el experimento (ver tracking.experiment_id).
REUBICAR = {"m1b-i1-seed0": "warehouse-m1b", "m1b-i1-seed1": "warehouse-m1b"}
LOTE = 900  # MLflow acepta hasta 1000 entidades por log_batch


def reintentar(fn, *args, intentos=5, **kw):
    for i in range(intentos):
        try:
            return fn(*args, **kw)
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(2 ** i)


def experimento_destino(dst: MlflowClient, nombre: str, cache: dict) -> str:
    if nombre not in cache:
        e = dst.get_experiment_by_name(nombre)
        cache[nombre] = e.experiment_id if e else dst.create_experiment(nombre)
    return cache[nombre]


def ya_migrados(dst: MlflowClient, exp_ids: list[str]) -> dict[str, tuple[str, bool]]:
    """origen_run_id -> (run_id destino, completo)."""
    out, token = {}, None
    while True:
        page = dst.search_runs(exp_ids, max_results=500, page_token=token)
        for r in page:
            o = r.data.tags.get("origen_run_id")
            if o:
                out[o] = (r.info.run_id, r.data.tags.get("migracion") == "completa")
        token = page.token
        if not token:
            return out


def copiar_run(src: MlflowClient, dst: MlflowClient, run, exp_id: str) -> str:
    info, data = run.info, run.data
    tags = {k: v for k, v in data.tags.items() if not k.startswith("mlflow.log-model")}
    tags["origen_run_id"] = info.run_id
    tags["origen_experimento"] = src.get_experiment(info.experiment_id).name
    status = info.status
    if status == "RUNNING":  # proceso muerto sin cerrar el run
        status, tags["migracion_nota"] = "KILLED", "RUNNING en origen sin proceso vivo; cerrado como KILLED"
        tags.update(estado="interrumpido", sin_checkpoint="true")

    nuevo = reintentar(dst.create_run, exp_id, start_time=info.start_time,
                       tags={"mlflow.runName": info.run_name}, run_name=info.run_name).info.run_id

    params = [Param(k, v) for k, v in data.params.items()]
    tag_list = [RunTag(k, v) for k, v in tags.items() if k != "mlflow.runName"]
    metrics = []
    for key in data.metrics:
        metrics += [Metric(m.key, m.value, m.timestamp, m.step) for m in src.get_metric_history(info.run_id, key)]

    for i in range(0, len(params), 100):
        reintentar(dst.log_batch, nuevo, params=params[i:i + 100])
    for i in range(0, len(tag_list), 100):
        reintentar(dst.log_batch, nuevo, tags=tag_list[i:i + 100])
    for i in range(0, len(metrics), LOTE):
        reintentar(dst.log_batch, nuevo, metrics=metrics[i:i + LOTE])

    local = Path(info.artifact_uri.removeprefix("file://"))
    if local.is_dir() and any(local.iterdir()):
        reintentar(dst.log_artifacts, nuevo, str(local))

    reintentar(dst.set_tag, nuevo, "migracion", "completa")
    reintentar(dst.set_terminated, nuevo, status=status, end_time=info.end_time)
    return nuevo


def actualizar_manifiestos(mapa: dict, destino: str) -> int:
    """mlflow_run_id -> id del servidor; el id local queda en mlflow_run_id_local."""
    n = 0
    for p in sorted(Path("manifests").glob("*.json")):
        if p.name == "schema.json":
            continue
        m = json.loads(p.read_text())
        viejo = m.get("mlflow_run_id")
        if viejo in mapa:
            m["mlflow_run_id_local"] = viejo
            m["mlflow_run_id"] = mapa[viejo]["nuevo_run_id"]
            m["mlflow_tracking_uri"] = destino
            p.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", help="nombre de run: copiar solo ese (prueba)")
    ap.add_argument("--hilos", type=int, default=6)
    ap.add_argument("--manifiestos", action="store_true",
                    help="solo reescribir manifests/ con el mapa ya guardado")
    args = ap.parse_args()

    destino = os.environ.get("MLFLOW_TRACKING_URI", "")
    if not destino.startswith("http"):
        raise SystemExit("MLFLOW_TRACKING_URI no apunta a un servidor; carga .env primero")
    if args.manifiestos:
        print(f"manifiestos actualizados: {actualizar_manifiestos(json.loads(MAPA.read_text()), destino)}")
        return
    src, dst = MlflowClient(ORIGEN), MlflowClient(destino)

    trabajos, cache = [], {}
    for e in src.search_experiments():
        for r in src.search_runs([e.experiment_id], max_results=1000):
            if args.solo and r.info.run_name != args.solo:
                continue
            nombre = REUBICAR.get(r.info.run_name, e.name) if e.name == "Default" else e.name
            trabajos.append((r, experimento_destino(dst, nombre, cache)))

    hechos = ya_migrados(dst, list(cache.values())) if cache else {}
    mapa = json.loads(MAPA.read_text()) if MAPA.exists() else {}
    pendientes = []
    for r, exp_id in trabajos:
        previo = hechos.get(r.info.run_id)
        if previo and previo[1]:
            mapa[r.info.run_id] = {"run_name": r.info.run_name, "nuevo_run_id": previo[0]}
            continue
        if previo:
            dst.delete_run(previo[0])
        pendientes.append((r, exp_id))
    print(f"{len(trabajos)} runs, {len(trabajos) - len(pendientes)} ya migrados, {len(pendientes)} por copiar")

    errores = []
    with ThreadPoolExecutor(args.hilos) as pool:
        fut = {pool.submit(copiar_run, src, dst, r, exp_id): r for r, exp_id in pendientes}
        for i, f in enumerate(as_completed(fut), 1):
            r = fut[f]
            try:
                mapa[r.info.run_id] = {"run_name": r.info.run_name, "nuevo_run_id": f.result()}
                print(f"[{i}/{len(pendientes)}] ok {r.info.run_name}", flush=True)
            except Exception as exc:
                errores.append(r.info.run_name)
                print(f"[{i}/{len(pendientes)}] ERROR {r.info.run_name}: {type(exc).__name__}: {exc}"[:400], flush=True)

    MAPA.parent.mkdir(parents=True, exist_ok=True)
    MAPA.write_text(json.dumps(dict(sorted(mapa.items())), indent=1, ensure_ascii=False) + "\n")
    print(f"mapa: {MAPA} ({len(mapa)} runs); errores: {errores or 'ninguno'}")
    if errores:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
