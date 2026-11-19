"""Modelos que sirve la API: políticas PPO exportadas a NumPy, verificadas contra su manifiesto, en caché.

La API corre en Render Free (0.1 CPU, 512 MB): no importa torch ni SB3 ni usa DVC (docs/decisiones.md, 2026-11-18).
Cada modelo servible tiene en Git `models/numpy/<run_id>.npz` y su ficha `models/numpy/<run_id>.json`, generados y
verificados contra SB3 (0 acciones distintas) por `pipelines/exportar_numpy.py`. Al cargar se comprueba la cadena:

  manifiesto (`model_sha256`) == ficha (`model_sha256`)  y  sha256(.npz) == ficha (`npz_sha256`)

Si algo no coincide el modelo no se carga (error `integridad`). La política es `PoliticaNumpy`, la misma clase que
verificó el exportador; cuenta decisiones y casi empates para `/monitoreo`.

- Fuente de verdad: `manifests/` + `manifests/aliases.json` (vía `pipelines.registry`) del commit desplegado; el modelo
  servido es `produccion.actual`.
- Caché LRU por SHA-256 del modelo. `produccion.actual` y `produccion.anterior` quedan fijos (precargados al arrancar,
  nunca desalojados): un rollback sirve de inmediato.
- Solo PPO de la versión de ambiente de este código (`ENV_VERSION`); los de versiones anteriores se evalúan desde su
  `runtime_ref`, no aquí.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

from pipelines import registry
from pipelines.exportar_numpy import FORMATO, PoliticaNumpy
from pipelines.tracking import sha256_file


class ErrorModelo(Exception):
    """Error con código estable y estado HTTP sugerido; la API lo convierte en {"error": {...}}."""

    def __init__(self, codigo: str, mensaje: str, estado_http: int, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.estado_http, self.detalle = codigo, mensaje, estado_http, detalle or {}


@dataclass
class ModeloCargado:
    run_id: str
    model_sha256: str
    npz_sha256: str
    level_id: str
    environment_version: str
    manifiesto: dict
    ficha: dict
    politica: PoliticaNumpy  # .action(observación, env) determinista; .monitoreo() decisiones y casi empates
    segundos_carga: float
    cargado_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    usos: int = 0

    def resumen(self, fijo: bool) -> dict:
        return {"run_id": self.run_id, "model_sha256": self.model_sha256, "npz_sha256": self.npz_sha256,
                "level_id": self.level_id, "environment_version": self.environment_version,
                "inferencia": "numpy", "segundos_carga": round(self.segundos_carga, 4), "cargado_en": self.cargado_en,
                "usos": self.usos, "fijo": fijo, **self.politica.monitoreo()}


class AlmacenModelos:
    """Caché de políticas NumPy verificadas. Seguro entre hilos (FastAPI ejecuta rutas síncronas en un pool)."""

    def __init__(self, raiz: Path = registry.RAIZ, capacidad: int = 4):
        if capacidad < 1:
            raise ValueError("capacidad >= 1")
        self.raiz = Path(raiz)
        self.capacidad = capacidad  # modelos no fijos en memoria; los fijos no cuentan
        self._cache: OrderedDict[str, ModeloCargado] = OrderedDict()
        self._fijos: set[str] = set()
        self._lock = threading.RLock()       # estado de la caché
        self._lock_carga = threading.Lock()  # una carga a la vez (evita cargar dos veces el mismo modelo)
        self.precarga: dict = {"estado": "sin ejecutar"}

    # --- Manifiestos -----------------------------------------------------------------------------

    def manifiesto_servible(self, run_id: str) -> dict:
        """Manifiesto válido de un modelo que esta API puede cargar; si no, ErrorModelo 404/409."""
        from envs import ENV_VERSION

        try:
            manifest = registry.cargar_manifiesto(run_id, self.raiz)
        except registry.RegistroError as exc:
            raise ErrorModelo("modelo_no_encontrado", f"No hay un manifiesto válido para '{run_id}'", 404,
                              {"run_id": run_id, "causa": str(exc)[:300]}) from None
        if manifest["environment_version"] != ENV_VERSION:
            raise ErrorModelo("modelo_incompatible",
                              f"{run_id} es de {manifest['environment_version']} y esta API ejecuta {ENV_VERSION}",
                              409, {"run_id": run_id, "environment_version": manifest["environment_version"],
                                    "runtime_ref": manifest["runtime_ref"]})
        algoritmo = (manifest.get("algorithm") or "PPO").upper()
        if algoritmo != "PPO":
            raise ErrorModelo("modelo_incompatible", f"{run_id} usa {algoritmo}; la API solo sirve PPO", 409,
                              {"run_id": run_id, "algorithm": algoritmo})
        return manifest

    def _rutas(self, run_id: str) -> tuple[Path, Path]:
        base = self.raiz / "models/numpy"
        return base / f"{run_id}.npz", base / f"{run_id}.json"

    def servibles(self) -> list[str]:
        """run_id con versión NumPy publicada (ficha presente); la integridad se comprueba al cargar."""
        return sorted(p.stem for p in (self.raiz / "models/numpy").glob("*.json"))

    # --- Carga -----------------------------------------------------------------------------------

    def obtener(self, run_id: str) -> ModeloCargado:
        """Política lista para inferir; verifica manifiesto, ficha y sha256 del .npz la primera vez."""
        manifest = self.manifiesto_servible(run_id)
        sha = manifest["model_sha256"]
        cargado = self._de_cache(sha)
        if cargado:
            return cargado
        with self._lock_carga:
            cargado = self._de_cache(sha)  # otro hilo pudo cargarlo mientras se esperaba el lock
            if cargado:
                return cargado
            cargado = self._cargar(manifest)
        with self._lock:
            self._cache[sha] = cargado
            self._desalojar()
            cargado.usos += 1
        return cargado

    def _de_cache(self, sha: str) -> ModeloCargado | None:
        with self._lock:
            cargado = self._cache.get(sha)
            if cargado:
                self._cache.move_to_end(sha)
                cargado.usos += 1
            return cargado

    def _cargar(self, manifest: dict) -> ModeloCargado:
        run_id = manifest["run_id"]
        inicio = time.perf_counter()
        npz, ficha_path = self._rutas(run_id)
        if not ficha_path.is_file() or not npz.is_file():
            raise ErrorModelo("sin_version_numpy", f"{run_id} no tiene versión NumPy publicada (models/numpy/)", 409,
                              {"run_id": run_id, "generar": f"python -m pipelines.exportar_numpy --run-id {run_id}"})
        try:
            ficha = json.loads(ficha_path.read_text())
        except json.JSONDecodeError as exc:
            raise ErrorModelo("integridad", f"La ficha de {run_id} no es JSON válido", 500, {"causa": str(exc)}) from None
        sha_npz = sha256_file(npz)
        detalle = {"run_id": run_id, "model_sha256_manifiesto": manifest["model_sha256"],
                   "model_sha256_ficha": ficha.get("model_sha256"), "npz_sha256_ficha": ficha.get("npz_sha256"),
                   "npz_sha256_real": sha_npz, "formato_ficha": ficha.get("formato_numpy"), "formato_api": FORMATO}
        if (ficha.get("run_id") != run_id or ficha.get("model_sha256") != manifest["model_sha256"]
                or ficha.get("npz_sha256") != sha_npz or ficha.get("formato_numpy") != FORMATO):
            raise ErrorModelo("integridad", f"{run_id}: la versión NumPy no coincide con su ficha o su manifiesto; "
                              "no se carga", 500, detalle)
        try:
            politica = PoliticaNumpy.desde_npz(npz)
        except Exception as exc:  # npz corrupto o con otra forma: nunca se sirve
            raise ErrorModelo("integridad", f"{run_id}: el .npz no se pudo cargar", 500,
                              {**detalle, "causa": f"{type(exc).__name__}: {exc}"[:300]}) from None
        return ModeloCargado(run_id=run_id, model_sha256=manifest["model_sha256"], npz_sha256=sha_npz,
                             level_id=manifest["level_id"], environment_version=manifest["environment_version"],
                             manifiesto=manifest, ficha=ficha, politica=politica,
                             segundos_carga=time.perf_counter() - inicio)

    def _desalojar(self) -> None:
        """Quita los menos usados recientemente hasta dejar `capacidad` modelos no fijos."""
        no_fijos = [sha for sha in self._cache if sha not in self._fijos]
        for sha in no_fijos[:max(0, len(no_fijos) - self.capacidad)]:
            del self._cache[sha]

    # --- Producción ------------------------------------------------------------------------------

    def ranura_produccion(self) -> dict:
        """{"actual": run_id, "anterior": run_id|None} según aliases.json del commit desplegado."""
        try:
            return registry.cargar_aliases(self.raiz)["ranuras"][registry.PRODUCCION]
        except (registry.RegistroError, KeyError) as exc:
            raise ErrorModelo("sin_produccion", "aliases.json no define la ranura de producción", 500,
                              {"causa": str(exc)[:300]}) from None

    def servido(self) -> dict:
        """Identidad del modelo de producción (lo que compara la etapa 8 del flujo), sin cargarlo."""
        ranura = self.ranura_produccion()
        actual = registry.cargar_manifiesto(ranura["actual"], self.raiz)
        return {"run_id": actual["run_id"], "model_sha256": actual["model_sha256"],
                "environment_version": actual["environment_version"], "level_id": actual["level_id"],
                "anterior": ranura.get("anterior")}

    def precargar_produccion(self) -> dict:
        """Verifica, carga y fija `produccion.actual` y `produccion.anterior`. No lanza nunca: cualquier error (también
        uno inesperado) queda en `self.precarga` para /health y /version, y la API sigue arrancando."""
        inicio = time.perf_counter()
        resultado = {"inicio": datetime.now(timezone.utc).isoformat(), "modelos": {}}
        try:
            ranura = self.ranura_produccion()
            for papel in ("actual", "anterior"):
                run_id = ranura.get(papel)
                if not run_id:
                    continue
                try:
                    cargado = self.obtener(run_id)
                    with self._lock:
                        self._fijos.add(cargado.model_sha256)
                    resultado["modelos"][papel] = {"run_id": run_id, "ok": True,
                                                   "segundos": round(cargado.segundos_carga, 4)}
                except ErrorModelo as exc:
                    resultado["modelos"][papel] = {"run_id": run_id, "ok": False, "codigo": exc.codigo,
                                                   "mensaje": exc.mensaje, "detalle": exc.detalle}
                except Exception as exc:  # inesperado: se informa en vez de matar el hilo de precarga
                    resultado["modelos"][papel] = {"run_id": run_id, "ok": False, "codigo": "error_interno",
                                                   "mensaje": f"{type(exc).__name__}: {exc}"[:300]}
            ok = [m["ok"] for m in resultado["modelos"].values()]
            resultado["estado"] = "ok" if ok and all(ok) else ("parcial" if any(ok) else "fallido")
        except ErrorModelo as exc:
            resultado.update(estado="fallido", error={"codigo": exc.codigo, "mensaje": exc.mensaje})
        except Exception as exc:
            resultado.update(estado="fallido", error={"codigo": "error_interno",
                                                      "mensaje": f"{type(exc).__name__}: {exc}"[:300]})
        resultado["segundos"] = round(time.perf_counter() - inicio, 4)
        self.precarga = resultado
        return resultado

    # --- Estado ----------------------------------------------------------------------------------

    def estado(self) -> dict:
        with self._lock:
            cargados = [m.resumen(sha in self._fijos) for sha, m in self._cache.items()]
        return {"capacidad_no_fijos": self.capacidad, "inferencia": "numpy", "cargados": cargados,
                "casi_empates": sum(m["casi_empates"] for m in cargados),
                "decisiones": sum(m["decisiones"] for m in cargados), "precarga": self.precarga}
