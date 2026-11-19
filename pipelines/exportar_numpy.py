"""Exporta políticas PPO (Stable-Baselines3) a NumPy para servirlas sin PyTorch, verificadas contra SB3.

La API corre en Render Free (0.1 CPU, 512 MB): con torch el proceso ocupa ~368 MB y su importación domina el
arranque en frío; con NumPy, ~57 MB (docs/decisiones.md, 2026-11-18). Este módulo:

- extrae la red de acción de un `model.zip` PPO (`policy_net`: Linear → Tanh → Linear → Tanh; `action_net`:
  Linear); la acción determinista es argmax de los logits, igual que `model.predict(deterministic=True)`;
- la verifica paso a paso contra SB3 en las suites del mapa con muro (estados reales de episodios guiados por SB3):
  **solo publica si hay 0 acciones distintas**; además registra la diferencia máxima de logits y el margen mínimo
  entre las dos mejores acciones (riesgo de empate);
- escribe `models/numpy/<run_id>.npz` (zip con fecha fija: el sha256 es reproducible) y su ficha
  `models/numpy/<run_id>.json`, ligada al `model_sha256` del manifiesto (los manifiestos no se editan);
- reutiliza un `.npz` idéntico y nunca sobrescribe uno distinto.

`PoliticaNumpy` (la misma clase que verifica este módulo) es la que usa la API: este archivo solo importa NumPy
a nivel de módulo; torch y SB3 se importan dentro de las funciones de conversión.

Uso (en una máquina con torch y los pesos de DVC):
  python -m pipelines.exportar_numpy --todos
  python -m pipelines.exportar_numpy --run-id m1-c3-seed0 [--run-id ...]
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import threading
import zipfile

import numpy as np

FORMATO = 1
CAPAS = (("capa0_w", "mlp_extractor.policy_net.0.weight"), ("capa0_b", "mlp_extractor.policy_net.0.bias"),
         ("capa1_w", "mlp_extractor.policy_net.2.weight"), ("capa1_b", "mlp_extractor.policy_net.2.bias"),
         ("accion_w", "action_net.weight"), ("accion_b", "action_net.bias"))
MARGEN_EMPATE = 1e-4  # margen top1 − top2 de logits por debajo del cual una decisión cuenta como casi empate
SUITES_MAPA_CON_MURO = ("suite-m1-v1", "suite-m1b-v1")  # paso (6,14) abierto y cerrado
RAIZ = Path(__file__).resolve().parents[1]


class ExportError(RuntimeError):
    """El modelo no se puede exportar o no pasó la verificación (nada se publica)."""


# --- Inferencia (sin torch) ------------------------------------------------------------------------

class PoliticaNumpy:
    """Red de acción PPO en float32: tanh(W0·o + b0) → tanh(W1·h + b1) → logits = Wa·h + ba → argmax.
    Cuenta las decisiones y los casi empates (margen < MARGEN_EMPATE) para el monitoreo de la API."""

    def __init__(self, capas: dict[str, np.ndarray]):
        faltan = [n for n, _ in CAPAS if n not in capas]
        if faltan:
            raise ExportError(f"faltan capas: {faltan}")
        self.w = [np.ascontiguousarray(capas[n], dtype=np.float32) for n, _ in CAPAS]
        w0, b0, w1, b1, wa, ba = self.w
        if not (w0.ndim == w1.ndim == wa.ndim == 2 and b0.shape == (w0.shape[0],) and w1.shape == (w1.shape[0], w0.shape[0])
                and b1.shape == (w1.shape[0],) and wa.shape[1] == w1.shape[0] and ba.shape == (wa.shape[0],)):
            raise ExportError(f"formas incompatibles: {[a.shape for a in self.w]}")
        self.n_obs, self.n_acciones = w0.shape[1], wa.shape[0]
        self.decisiones = self.casi_empates = 0
        self._lock = threading.Lock()

    @classmethod
    def desde_npz(cls, path) -> "PoliticaNumpy":
        with np.load(path, allow_pickle=False) as z:
            return cls({n: z[n] for n, _ in CAPAS})

    def logits(self, observation) -> np.ndarray:
        w0, b0, w1, b1, wa, ba = self.w
        o = np.asarray(observation, dtype=np.float32)
        h = np.tanh(w0 @ o + b0)
        h = np.tanh(w1 @ h + b1)
        return wa @ h + ba

    def action(self, observation, env=None) -> int:
        logits = self.logits(observation)
        accion = int(np.argmax(logits))
        dos = np.partition(logits, -2)[-2:]
        with self._lock:
            self.decisiones += 1
            self.casi_empates += int(dos[1] - dos[0] < MARGEN_EMPATE)
        return accion

    def monitoreo(self) -> dict:
        with self._lock:
            return {"decisiones": self.decisiones, "casi_empates": self.casi_empates, "margen": MARGEN_EMPATE}


def npz_bytes(capas: dict[str, np.ndarray]) -> bytes:
    """Zip sin compresión con fecha, permisos y sistema fijos: mismos pesos → mismos bytes → mismo sha256."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as z:
        for nombre, _ in CAPAS:
            datos = io.BytesIO()
            np.lib.format.write_array(datos, np.ascontiguousarray(capas[nombre], dtype="<f4"), allow_pickle=False)
            info = zipfile.ZipInfo(f"{nombre}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system, info.external_attr = 0, 0o644 << 16
            z.writestr(info, datos.getvalue())
    return buffer.getvalue()


# --- Conversión y verificación (con torch) ---------------------------------------------------------

def extraer_capas(model) -> dict[str, np.ndarray]:
    """Capas de la red de acción, comprobando que la arquitectura es la que reproduce PoliticaNumpy."""
    import torch.nn as nn
    from gymnasium import spaces
    from stable_baselines3.common.torch_layers import FlattenExtractor

    policy = model.policy
    red = list(policy.mlp_extractor.policy_net)
    esperado = [nn.Linear, nn.Tanh, nn.Linear, nn.Tanh]
    if [type(m) for m in red] != esperado or not isinstance(policy.action_net, nn.Linear):
        raise ExportError(f"arquitectura no soportada: {[type(m).__name__ for m in red]} + {type(policy.action_net).__name__}")
    if not isinstance(policy.pi_features_extractor, FlattenExtractor) or not isinstance(model.action_space, spaces.Discrete):
        raise ExportError("se espera FlattenExtractor y acciones Discrete")
    estado = policy.state_dict()
    return {nombre: estado[clave].detach().cpu().numpy().astype(np.float32) for nombre, clave in CAPAS}


def _suite(raiz: Path, suite_id: str) -> dict:
    import yaml

    datos = yaml.safe_load((raiz / "configs/suites" / f"{suite_id}.yaml").read_text())
    inicio, fin = datos["semillas_rango"]
    return {"id": suite_id, "semillas": list(range(inicio, fin + 1)), "bloqueado": datos.get("escenario") == "bloqueado"}


def verificar(model, politica: PoliticaNumpy, manifest: dict, suites: list[str], raiz: Path = RAIZ) -> dict:
    """Episodios guiados por SB3; en cada estado compara la acción NumPy con `model.predict(deterministic=True)`
    y los logits NumPy con los de torch."""
    import torch

    from envs import make_env

    policy = model.policy
    resultado = {}
    for suite_id in suites:
        suite = _suite(raiz, suite_id)
        pasos = distintas = 0
        dif_max, margen_min = 0.0, float("inf")
        for seed in suite["semillas"]:
            env = make_env(suite["bloqueado"], str(raiz / manifest["layout_path"]), 3, manifest.get("reward_overrides") or None)
            obs, _ = env.reset(seed=seed)
            fin = False
            while not fin:
                accion_sb3 = int(model.predict(obs, deterministic=True)[0])
                with torch.no_grad():
                    rasgos = policy.extract_features(torch.as_tensor(obs)[None], policy.pi_features_extractor)
                    logits_torch = policy.action_net(policy.mlp_extractor.forward_actor(rasgos))[0].numpy()
                logits = politica.logits(obs)
                dos = np.sort(logits)[-2:]
                dif_max = max(dif_max, float(np.abs(logits - logits_torch).max()))
                margen_min = min(margen_min, float(dos[1] - dos[0]))
                distintas += int(np.argmax(logits)) != accion_sb3
                pasos += 1
                obs, _, terminado, truncado, _ = env.step(accion_sb3)
                fin = terminado or truncado
            env.close()
        resultado[suite_id] = {"episodios": len(suite["semillas"]), "pasos": pasos, "acciones_distintas": distintas,
                               "max_dif_logit": dif_max, "margen_min_logit": margen_min}
    return resultado


def _versiones() -> dict:
    from importlib.metadata import version

    return {p: version(p) for p in ("stable-baselines3", "torch", "numpy", "gymnasium")}


def exportar(run_id: str, *, raiz: Path = RAIZ, salida: Path | None = None) -> dict:
    """Exporta y verifica un modelo. Devuelve el resumen; lanza ExportError si no se puede publicar."""
    from stable_baselines3 import PPO

    from envs import ENV_VERSION
    from pipelines import registry
    from pipelines.tracking import git_info

    raiz = Path(raiz)
    salida = Path(salida) if salida else raiz / "models/numpy"
    manifest = registry.cargar_manifiesto(run_id, raiz)
    if manifest["environment_version"] != ENV_VERSION or (manifest.get("algorithm") or "PPO").upper() != "PPO":
        raise ExportError(f"{run_id}: solo PPO de {ENV_VERSION} (es {manifest.get('algorithm')} de {manifest['environment_version']})")
    if manifest.get("normalization_uri"):
        raise ExportError(f"{run_id}: tiene normalización ({manifest['normalization_uri']}); este formato no la incluye")
    origen = registry.verificar_modelo(run_id, descargar=True, raiz=raiz)  # sha256 del zip = manifiesto
    if not origen["ok"]:
        raise ExportError(f"{run_id}: {origen.get('error')}")

    model = PPO.load(str(raiz / manifest["model_uri"]), device="cpu")
    capas = extraer_capas(model)
    datos = npz_bytes(capas)
    sha_npz = sha256(datos).hexdigest()
    npz, ficha_path = salida / f"{run_id}.npz", salida / f"{run_id}.json"
    if npz.is_file():
        if sha256(npz.read_bytes()).hexdigest() != sha_npz:
            raise ExportError(f"{npz} existe con otro contenido; no se sobrescribe (revísalo o sube FORMATO)")
        if ficha_path.is_file():
            ficha = json.loads(ficha_path.read_text())
            if ficha.get("model_sha256") == manifest["model_sha256"] and ficha.get("npz_sha256") == sha_npz:
                return {"run_id": run_id, "estado": "reutilizado", "npz_sha256": sha_npz,
                        "verificacion": ficha["verificacion"]}

    politica = PoliticaNumpy.desde_npz(io.BytesIO(datos))  # se verifica lo que se va a publicar, leído del archivo
    suites = sorted({manifest["evaluation_suite_id"], *SUITES_MAPA_CON_MURO}) \
        if manifest.get("layout_path") == "configs/layout_v0.4.json" else [manifest["evaluation_suite_id"]]
    verificacion = verificar(model, politica, manifest, suites, raiz)
    distintas = sum(v["acciones_distintas"] for v in verificacion.values())
    if distintas:
        raise ExportError(f"{run_id}: {distintas} acciones distintas frente a SB3; no se publica ({verificacion})")

    salida.mkdir(parents=True, exist_ok=True)
    if not npz.is_file():
        with npz.open("xb") as handle:  # «x»: nunca sobrescribe
            handle.write(datos)
    git = git_info()
    ficha = {
        "formato_numpy": FORMATO, "run_id": run_id, "level_id": manifest["level_id"],
        "environment_version": manifest["environment_version"],
        "model_uri": manifest["model_uri"], "model_sha256": manifest["model_sha256"],
        "npz_uri": str(npz.relative_to(raiz)) if npz.is_relative_to(raiz) else str(npz), "npz_sha256": sha_npz,
        "red": {"capas": [{"nombre": n, "origen": c, "forma": list(capas[n].shape)} for n, c in CAPAS],
                "activacion": "tanh", "accion": "argmax(logits), determinista", "dtype": "float32",
                "observacion": f"Box({politica.n_obs}) sin normalizar (envs/CONTRATO.md)",
                "acciones": f"Discrete({politica.n_acciones})"},
        "verificacion": {"criterio": "0 acciones distintas frente a model.predict(deterministic=True)",
                         "acciones_distintas": 0, "pasos": sum(v["pasos"] for v in verificacion.values()),
                         "max_dif_logit": max(v["max_dif_logit"] for v in verificacion.values()),
                         "margen_min_logit": min(v["margen_min_logit"] for v in verificacion.values()),
                         "por_suite": verificacion},
        "versiones": _versiones(), "conversor": {"script": "pipelines/exportar_numpy.py", **git},
        "creado_en": datetime.now(timezone.utc).isoformat(),
    }
    tmp = ficha_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(ficha, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(ficha_path)
    return {"run_id": run_id, "estado": "exportado", "npz_sha256": sha_npz, "verificacion": ficha["verificacion"]}


def candidatos(raiz: Path = RAIZ) -> list[str]:
    """Manifiestos PPO de la versión de ambiente actual (los que la API puede servir)."""
    from envs import ENV_VERSION
    from pipelines import registry

    validos, _ = registry.listar_manifiestos(raiz)
    return sorted(r for r, m in validos.items()
                  if m["environment_version"] == ENV_VERSION and (m.get("algorithm") or "PPO").upper() == "PPO")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Exporta políticas PPO a NumPy verificadas contra SB3")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--todos", action="store_true", help="todos los PPO de la versión de ambiente actual")
    grupo.add_argument("--run-id", action="append", dest="runs")
    parser.add_argument("--salida", type=Path, help="carpeta de salida (por defecto models/numpy)")
    args = parser.parse_args(argv)
    import torch

    torch.set_num_threads(1)
    resultados, fallidos = [], []
    for run_id in (candidatos() if args.todos else args.runs):
        try:
            r = exportar(run_id, salida=args.salida)
            v = r["verificacion"]
            print(f"{run_id}: {r['estado']} npz {r['npz_sha256'][:12]} | {v['pasos']} pasos, 0 distintas, "
                  f"dif máx {v['max_dif_logit']:.1e}, margen mín {v['margen_min_logit']:.1e}", flush=True)
            resultados.append(r)
        except Exception as exc:  # un modelo que falla no detiene a los demás; queda en el resumen
            print(f"{run_id}: NO PUBLICADO: {exc}"[:400], file=sys.stderr, flush=True)
            fallidos.append({"run_id": run_id, "error": f"{type(exc).__name__}: {exc}"[:1000]})
    print(json.dumps({"exportados": len(resultados), "fallidos": fallidos}, ensure_ascii=False))
    return 1 if fallidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
