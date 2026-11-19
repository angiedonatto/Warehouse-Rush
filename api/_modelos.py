"""Modelos que sirve la API: descarga desde R2 (DVC), verificación de SHA-256 y caché en memoria.

Fuente de verdad: `manifests/` + `manifests/aliases.json` (vía `pipelines.registry`), los mismos que van dentro
de la imagen del Space; el modelo servido es `produccion.actual` del commit desplegado.

- Descarga: `registry.verificar_modelo(descargar=True)` → `dvc pull models/<run>.dvc`. En el contenedor no hay
  `.git`, así que la imagen fija `dvc config --local core.no_scm true`; las credenciales de R2 llegan como
  secrets `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (token de solo lectura). Verificado 2026-11-18 en una
  copia sin `.git`: sin `no_scm` falla («is not a git repository»), con `no_scm` descarga y el sha256 coincide.
- DVC no admite dos `pull` a la vez («Unable to acquire lock»): las descargas se serializan con un lock y la API
  corre con un solo worker de Uvicorn.
- Nunca se carga un archivo cuyo SHA-256 no coincida con su manifiesto.
- Caché LRU por SHA-256. `produccion.actual` y `produccion.anterior` quedan fijos (precargados al arrancar y
  nunca desalojados), así un rollback sirve de inmediato sin descargar.
- Solo se cargan modelos PPO de la versión de ambiente de este código (`ENV_VERSION`); los de versiones
  anteriores se evalúan desde su `runtime_ref`, no aquí.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import threading
import time

from pipelines import registry


class ErrorModelo(Exception):
    """Error con código estable y estado HTTP sugerido; la API lo convierte en {"error": {...}}."""

    def __init__(self, codigo: str, mensaje: str, estado_http: int, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.estado_http, self.detalle = codigo, mensaje, estado_http, detalle or {}


@dataclass
class ModeloCargado:
    run_id: str
    model_sha256: str
    level_id: str
    environment_version: str
    manifiesto: dict
    politica: object  # pipelines.baselines.PPOPolicy: .action(observación, env) determinista
    origen: str  # "disco" (ya estaba) o "dvc" (descargado de R2)
    segundos_carga: float
    cargado_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    usos: int = 0

    def resumen(self, fijo: bool) -> dict:
        return {"run_id": self.run_id, "model_sha256": self.model_sha256, "level_id": self.level_id,
                "environment_version": self.environment_version, "origen": self.origen,
                "segundos_carga": round(self.segundos_carga, 3), "cargado_en": self.cargado_en,
                "usos": self.usos, "fijo": fijo}


class AlmacenModelos:
    """Caché de políticas PPO verificadas. Seguro entre hilos (FastAPI ejecuta rutas síncronas en un pool)."""

    def __init__(self, raiz: Path = registry.RAIZ, capacidad: int = 4):
        if capacidad < 1:
            raise ValueError("capacidad >= 1")
        self.raiz = Path(raiz)
        self.capacidad = capacidad  # modelos no fijos en memoria; los fijos no cuentan
        self._cache: OrderedDict[str, ModeloCargado] = OrderedDict()
        self._fijos: set[str] = set()
        self._lock = threading.RLock()          # estado de la caché
        self._lock_carga = threading.Lock()     # descarga con DVC + carga: una a la vez
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

    # --- Carga -----------------------------------------------------------------------------------

    def obtener(self, run_id: str) -> ModeloCargado:
        """Política lista para inferir. Descarga (DVC) y verifica el SHA-256 si no está en memoria."""
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
        import torch

        from pipelines.baselines import PPOPolicy

        run_id = manifest["run_id"]
        inicio = time.perf_counter()
        verificado = registry.verificar_modelo(run_id, descargar=True, raiz=self.raiz)
        if not verificado["ok"]:
            detalle = {k: verificado.get(k) for k in ("run_id", "model_uri", "esperado", "real", "presente", "error")}
            if verificado["presente"]:  # el archivo existe pero su hash no es el del manifiesto
                raise ErrorModelo("integridad", f"El SHA-256 de {run_id} no coincide con su manifiesto; no se carga",
                                  500, detalle)
            raise ErrorModelo("pesos_no_disponibles", f"No se pudieron obtener los pesos de {run_id} desde R2",
                              503, detalle)
        torch.set_num_threads(1)
        politica = PPOPolicy(str(self.raiz / manifest["model_uri"]))
        return ModeloCargado(run_id=run_id, model_sha256=verificado["real"], level_id=manifest["level_id"],
                             environment_version=manifest["environment_version"], manifiesto=manifest,
                             politica=politica, origen="dvc" if verificado["descargado"] else "disco",
                             segundos_carga=time.perf_counter() - inicio)

    def _desalojar(self) -> None:
        """Quita los menos usados recientemente hasta dejar `capacidad` modelos no fijos."""
        no_fijos = [sha for sha in self._cache if sha not in self._fijos]
        for sha in no_fijos[:max(0, len(no_fijos) - self.capacidad)]:
            del self._cache[sha]

    # --- Producción ------------------------------------------------------------------------------

    def ranura_produccion(self) -> dict:
        """{"actual": run_id, "anterior": run_id|None} según aliases.json de la imagen."""
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
        """Descarga, verifica y fija `produccion.actual` y `produccion.anterior`. No lanza: deja el resultado
        en `self.precarga` para /health y /version (la API arranca aunque R2 falle y lo informa)."""
        inicio = time.perf_counter()
        resultado = {"inicio": datetime.now(timezone.utc).isoformat(), "modelos": {}}
        try:
            ranura = self.ranura_produccion()
        except ErrorModelo as exc:
            resultado.update(estado="fallido", error={"codigo": exc.codigo, "mensaje": exc.mensaje})
            self.precarga = resultado
            return resultado
        for papel in ("actual", "anterior"):
            run_id = ranura.get(papel)
            if not run_id:
                continue
            try:
                cargado = self.obtener(run_id)
                with self._lock:
                    self._fijos.add(cargado.model_sha256)
                resultado["modelos"][papel] = {"run_id": run_id, "ok": True, "origen": cargado.origen,
                                               "segundos": round(cargado.segundos_carga, 3)}
            except ErrorModelo as exc:
                resultado["modelos"][papel] = {"run_id": run_id, "ok": False, "codigo": exc.codigo,
                                               "mensaje": exc.mensaje, "detalle": exc.detalle}
        ok = [m["ok"] for m in resultado["modelos"].values()]
        resultado["estado"] = "ok" if ok and all(ok) else ("parcial" if any(ok) else "fallido")
        resultado["segundos"] = round(time.perf_counter() - inicio, 3)
        self.precarga = resultado
        return resultado

    # --- Estado ----------------------------------------------------------------------------------

    def estado(self) -> dict:
        with self._lock:
            cargados = [m.resumen(sha in self._fijos) for sha, m in self._cache.items()]
        return {"capacidad_no_fijos": self.capacidad, "cargados": cargados, "precarga": self.precarga}
