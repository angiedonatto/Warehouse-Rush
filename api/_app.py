"""API FastAPI de Warehouse Rush (Render, Docker): el único servidor de modelos y episodios (decisión del equipo,
2026-11-18). Catálogo, modelos, evaluaciones certificadas (asíncronas), episodios y monitoreo.

Arranque (un solo worker: episodios y evaluaciones viven en la memoria de un proceso, ver docs/decisiones.md):
  uvicorn api._app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1

Variables de entorno:
  CORS_ORIGINS        orígenes permitidos separados por coma, p. ej. https://warehouse-rush-experiment-001.vercel.app
  CORS_ORIGIN_REGEX   opcional, p. ej. para los previews del proyecto en Vercel
  GIT_COMMIT          opcional; si no, VERSION.json de la imagen o `git rev-parse HEAD` en local
  WAREHOUSE_PRECARGAR 0 para no precargar producción al arrancar (pruebas)

Inferencia en NumPy (models/numpy/, en Git): la imagen no lleva torch ni DVC ni credenciales.
Todas las respuestas llevan `X-Modelo-Servido: <run_id>@<sha12>` y `X-Git-Commit`. Los errores tienen una sola
forma: {"error": {"codigo", "mensaje", "detalle"}}. La simulación Python es la autoridad; la web solo dibuja.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from starlette.exceptions import HTTPException as StarletteHTTPException
import yaml

from api._episodios import CATALOGO_EPISODIOS, CATALOGO_SUITES, NIVELES, GestorEpisodios, Metricas, _orders
from api._modelos import AlmacenModelos, ErrorModelo
from pipelines import registry

log = logging.getLogger("warehouse.api")
EJEMPLO_ORIGEN = "https://warehouse-rush-experiment-001.vercel.app"


# --- Cuerpos de las peticiones (estrictos: "3" no es 3, campos desconocidos = 422) -----------------

class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CrearEpisodio(_Estricto):
    politica: Literal["ppo", "heuristic", "random", "manual"] = "ppo"
    run_id: str | None = None
    nivel: Literal["m1", "m1b", "m1o"] | None = None
    bloqueado: StrictBool | None = None
    seed: StrictInt = Field(10_000, ge=0, le=2**32 - 1)


class Paso(_Estricto):
    accion: StrictInt | None = Field(None, ge=0, le=7)


class Correr(_Estricto):
    max_pasos: StrictInt | None = Field(None, ge=1, le=400)


class Evaluar(_Estricto):
    suite_id: str
    politica: Literal["ppo", "heuristic", "random"] = "ppo"
    run_id: str | None = None  # ppo; sin él, el modelo de producción


# --- Utilidades ------------------------------------------------------------------------------------

def _git_commit(raiz: Path) -> str:
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    version = raiz / "VERSION.json"  # lo escribe la publicación de la imagen (la imagen no tiene .git)
    if version.is_file():
        return json.loads(version.read_text()).get("git_commit", "desconocido")
    try:  # en local; la imagen slim no trae el binario git
        proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True)
    except OSError:
        return "desconocido"
    return proc.stdout.strip() or "desconocido"


def _origenes() -> list[str]:
    return [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]


class MetricasHttp:
    """Peticiones, errores y latencia por ruta (plantilla de la ruta, no la URL concreta)."""

    def __init__(self, muestras: int = 1000):
        self._lock, self._muestras, self._rutas = threading.Lock(), muestras, {}

    def registrar(self, ruta: str, estado: int, ms: float) -> None:
        with self._lock:
            r = self._rutas.setdefault(ruta, {"peticiones": 0, "errores_4xx": 0, "errores_5xx": 0, "ms": []})
            r["peticiones"] += 1
            r["errores_4xx"] += 400 <= estado < 500
            r["errores_5xx"] += estado >= 500
            r["ms"] = (r["ms"] + [ms])[-self._muestras:]

    def resumen(self) -> dict:
        with self._lock:
            salida = {}
            for ruta, r in sorted(self._rutas.items()):
                orden = sorted(r["ms"])
                salida[ruta] = {k: r[k] for k in ("peticiones", "errores_4xx", "errores_5xx")}
                if orden:
                    salida[ruta].update(p50_ms=round(orden[len(orden) // 2], 2),
                                        p95_ms=round(orden[min(len(orden) - 1, int(0.95 * len(orden)))], 2))
            return salida


# --- Evaluaciones asíncronas -----------------------------------------------------------------------

class _ContadorEpisodios:
    """Envuelve la política inyectada en una evaluación: cuenta episodios (cada uno empieza con tiempo 0) para el
    progreso y mide cada decisión para /monitoreo. No cambia la acción."""

    def __init__(self, politica, al_decidir):
        self.politica, self.al_decidir, self.episodios = politica, al_decidir, 0

    def action(self, observation, env) -> int:
        if env.state.tiempo == 0:
            self.episodios += 1
        inicio = time.perf_counter()
        accion = self.politica.action(observation, env)
        self.al_decidir((time.perf_counter() - inicio) * 1000)
        return accion


class TrabajosEvaluacion:
    """Cola de evaluaciones: un hilo las corre de a una (Render Free tiene 0.1 CPU); hasta `cola_max` esperan
    (más → 429). Los resultados caducan `ttl_s` después de la última consulta una vez terminados."""

    def __init__(self, *, cola_max: int = 3, ttl_s: float = 30 * 60, reloj=time.monotonic):
        import queue

        self.cola_max, self.ttl_s, self._reloj = cola_max, ttl_s, reloj
        self._cola: queue.Queue = queue.Queue()
        self._trabajos: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._hilo: threading.Thread | None = None

    def encolar(self, descripcion: dict, tarea, contador=None) -> dict:
        import secrets

        with self._lock:
            self._purgar()
            esperando = sum(t["estado"] == "en_cola" for t in self._trabajos.values())
            if esperando >= self.cola_max:
                raise ErrorModelo("cola_llena", f"Ya hay {esperando} evaluaciones en cola; reintenta en un minuto", 429,
                                  {"en_cola": esperando, "cola_max": self.cola_max})
            id_ = secrets.token_urlsafe(9)
            self._trabajos[id_] = {"evaluacion_id": id_, "estado": "en_cola", **descripcion,
                                   "creada_en": datetime.now(timezone.utc).isoformat(),
                                   "sondeo": f"/evaluaciones/trabajos/{id_}",
                                   "_tarea": tarea, "_contador": contador, "_acceso": self._reloj()}
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(target=self._trabajar, name="evaluaciones", daemon=True)
                self._hilo.start()
        self._cola.put(id_)
        return self.ver(id_)

    def _trabajar(self) -> None:
        while True:
            id_ = self._cola.get()
            with self._lock:
                trabajo = self._trabajos.get(id_)
                if trabajo is None:
                    continue
                trabajo.update(estado="en_curso", iniciada_en=datetime.now(timezone.utc).isoformat())
            inicio = time.perf_counter()
            resultado, error = None, None
            try:
                resultado = trabajo["_tarea"]()
            except ErrorModelo as exc:
                error = {"codigo": exc.codigo, "mensaje": exc.mensaje, "detalle": exc.detalle}
            except Exception as exc:  # se informa en el trabajo; el hilo sigue atendiendo la cola
                log.exception("Evaluación %s fallida", id_)
                error = {"codigo": "error_interno", "mensaje": f"{type(exc).__name__}: {exc}"[:300], "detalle": {}}
            with self._lock:
                trabajo.update(estado="fallida" if error else "terminada", resultado=resultado, error=error,
                               terminada_en=datetime.now(timezone.utc).isoformat(),
                               segundos=round(time.perf_counter() - inicio, 2), _acceso=self._reloj())

    def _purgar(self) -> None:
        """Con el lock tomado: quita los terminados o fallidos sin consultar desde hace más de `ttl_s`."""
        ahora = self._reloj()
        for id_, t in list(self._trabajos.items()):
            if t["estado"] in ("terminada", "fallida") and ahora - t["_acceso"] > self.ttl_s:
                del self._trabajos[id_]

    def ver(self, id_: str) -> dict:
        with self._lock:
            self._purgar()
            trabajo = self._trabajos.get(id_)
            if trabajo is None:
                raise ErrorModelo("evaluacion_no_encontrada",
                                  "La evaluación no existe o caducó (30 min después de terminar)", 404,
                                  {"evaluacion_id": id_})
            trabajo["_acceso"] = self._reloj()
            vista = {k: v for k, v in trabajo.items() if not k.startswith("_")}
            contador = trabajo["_contador"]
            vista["progreso"] = {"episodios_hechos": (contador.episodios if contador else None)
                                 if trabajo["estado"] != "terminada" else trabajo["episodios"],
                                 "episodios_total": trabajo["episodios"]}
            if trabajo["estado"] == "en_cola":
                en_cola = [i for i, t in self._trabajos.items() if t["estado"] == "en_cola"]
                vista["posicion_en_cola"] = en_cola.index(id_) + 1
            return vista

    def estado(self) -> dict:
        with self._lock:
            self._purgar()
            cuenta = {}
            for t in self._trabajos.values():
                cuenta[t["estado"]] = cuenta.get(t["estado"], 0) + 1
            return {"por_estado": cuenta, "cola_max": self.cola_max, "ttl_s": self.ttl_s}


# --- Aplicación ------------------------------------------------------------------------------------

def create_app(raiz: Path = registry.RAIZ, *, almacen: AlmacenModelos | None = None,
               episodios: GestorEpisodios | None = None, precargar: bool | None = None) -> FastAPI:
    raiz = Path(raiz)
    almacen = almacen or AlmacenModelos(raiz)
    metricas = episodios.metricas if episodios else Metricas()
    episodios = episodios or GestorEpisodios(almacen, metricas=metricas)
    http = MetricasHttp()
    commit = _git_commit(raiz)
    iniciado = datetime.now(timezone.utc).isoformat()
    trabajos = TrabajosEvaluacion()  # evaluaciones certificadas, asíncronas, de a una (0.1 CPU en Render Free)
    if precargar is None:
        precargar = os.environ.get("WAREHOUSE_PRECARGAR", "1") != "0"

    @asynccontextmanager
    async def lifespan(_app):
        # Sin load_dotenv: la API no usa MLflow ni DVC (políticas NumPy en Git) y no debe copiar credenciales de .env
        # al proceso.
        if precargar:  # en segundo plano: el puerto abre ya y /health informa el progreso
            almacen.precarga = {"estado": "en curso"}
            threading.Thread(target=almacen.precargar_produccion, name="precarga", daemon=True).start()
        yield

    app = FastAPI(title="Warehouse Rush API", version="1.0.0", lifespan=lifespan,
                  description="Catálogo, carga y evaluación de modelos y episodios de la simulación warehouse-v10.")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(CORSMiddleware, allow_origins=_origenes(),
                       allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX") or None,
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
                       allow_credentials=False, expose_headers=["X-Modelo-Servido", "X-Git-Commit"], max_age=600)
    if not _origenes() and not os.environ.get("CORS_ORIGIN_REGEX"):
        log.warning("CORS_ORIGINS vacío: ningún navegador de otro origen podrá llamar a la API (ej.: %s)",
                    EJEMPLO_ORIGEN)

    def servido_cabecera() -> str:
        try:
            s = almacen.servido()
            return f"{s['run_id']}@{s['model_sha256'][:12]}"
        except Exception:
            return "desconocido"

    @app.middleware("http")
    async def cabeceras_y_metricas(request: Request, call_next):
        inicio = time.perf_counter()
        respuesta = await call_next(request)
        ruta = getattr(request.scope.get("route"), "path", "sin-ruta")
        http.registrar(f"{request.method} {ruta}", respuesta.status_code, (time.perf_counter() - inicio) * 1000)
        respuesta.headers["X-Modelo-Servido"] = servido_cabecera()
        respuesta.headers["X-Git-Commit"] = commit
        return respuesta

    # --- Errores: una sola forma ---------------------------------------------------------------

    def error(estado: int, codigo: str, mensaje: str, detalle=None) -> JSONResponse:
        return JSONResponse({"error": {"codigo": codigo, "mensaje": mensaje, "detalle": detalle or {}}}, estado)

    @app.exception_handler(ErrorModelo)  # incluye ErrorEpisodio
    async def _error_dominio(_request, exc: ErrorModelo):
        return error(exc.estado_http, exc.codigo, exc.mensaje, exc.detalle)

    @app.exception_handler(RequestValidationError)
    async def _error_validacion(_request, exc: RequestValidationError):
        detalle = [{"campo": ".".join(map(str, e["loc"][1:])) or "cuerpo", "problema": e["msg"]} for e in exc.errors()]
        return error(422, "parametro_invalido", "La petición no cumple el contrato de la API", {"errores": detalle})

    @app.exception_handler(StarletteHTTPException)
    async def _error_http(_request, exc: StarletteHTTPException):
        codigo = {404: "ruta_no_encontrada", 405: "metodo_no_permitido"}.get(exc.status_code, "error_http")
        return error(exc.status_code, codigo, str(exc.detail))

    @app.exception_handler(Exception)
    async def _error_interno(_request, exc: Exception):
        log.exception("Error no controlado")
        return error(500, "error_interno", f"{type(exc).__name__}: {exc}"[:300])

    # --- Servicio ------------------------------------------------------------------------------

    def catalogo_publicado() -> dict:
        return json.loads((raiz / "manifests/catalog.json").read_text())

    @app.get("/health")
    def health():
        """Viva siempre que el proceso responda; `degradado` si los modelos de producción no cargaron."""
        precarga = almacen.precarga.get("estado")
        return {"status": "degradado" if precarga in ("fallido", "parcial") else "ok", "precarga": precarga,
                "episodios": episodios.estado(), "iniciado_en": iniciado}

    @app.get("/version")
    def version():
        """Lo que compara la etapa 8 del flujo (run_id, model_sha256, environment_version) y la procedencia."""
        from envs import __version__ as ficha

        servido = almacen.servido()
        publicado = catalogo_publicado()
        return {**servido, "git_commit": commit, "environment_sheet_version": ficha,
                "catalogo": {"contenido_sha256": publicado["contenido_sha256"],
                             "aliases_version": publicado["aliases_version"],
                             "al_dia": publicado["contenido_sha256"] == registry.construir_catalogo(raiz)["contenido_sha256"]},
                "modelos_cargados": almacen.estado()["cargados"], "precarga": almacen.precarga,
                "iniciado_en": iniciado}

    # --- Catálogo y modelos --------------------------------------------------------------------

    @app.get("/catalogo")
    def catalogo(nivel: str | None = Query(None), estado: str | None = Query(None)):
        publicado = catalogo_publicado()
        modelos = [m for m in publicado["modelos"]
                   if (nivel is None or m["level_id"] == nivel) and (estado is None or m["estado"] == estado)]
        return {**publicado, "modelos": modelos, "filtro": {"nivel": nivel, "estado": estado}}

    @app.get("/catalogo/{run_id}")
    def ficha(run_id: str):
        entrada = next((m for m in catalogo_publicado()["modelos"] if m["run_id"] == run_id), None)
        if entrada is None:
            raise ErrorModelo("modelo_no_encontrado", f"'{run_id}' no está en el catálogo", 404, {"run_id": run_id})
        return {"modelo": entrada, "manifiesto": registry.cargar_manifiesto(run_id, raiz)}

    @app.post("/modelos/{run_id}/cargar")
    def cargar(run_id: str):
        cargado = almacen.obtener(run_id)
        fijo = any(m["fijo"] for m in almacen.estado()["cargados"] if m["model_sha256"] == cargado.model_sha256)
        return cargado.resumen(fijo)

    # --- Evaluaciones --------------------------------------------------------------------------

    def suite(suite_id: str) -> dict:
        path = raiz / "configs/suites" / f"{suite_id}.yaml"
        if suite_id.startswith("test-final") or Path(suite_id).name != suite_id or not path.is_file():
            raise ErrorModelo("suite_no_disponible", f"La suite '{suite_id}' no existe o es reservada", 404,
                              {"suite_id": suite_id})
        datos = yaml.safe_load(path.read_text())
        if datos.get("nivel") not in NIVELES:
            raise ErrorModelo("suite_no_disponible", f"{suite_id} es de una familia anterior a warehouse-v10", 409,
                              {"suite_id": suite_id, "nivel": datos.get("nivel")})
        semillas = (list(range(datos["semillas_rango"][0], datos["semillas_rango"][1] + 1))
                    if "semillas_rango" in datos else list(datos["semillas"]))
        if semillas != list(range(semillas[0], semillas[0] + len(semillas))) or len(semillas) != datos["episodios"]:
            raise ErrorModelo("suite_no_disponible", f"{suite_id}: semillas no contiguas o no cuadran", 500)
        return {**datos, "semillas": semillas, "bloqueado": datos.get("escenario", "abierto") == "bloqueado"}

    @app.get("/evaluaciones/{run_id}")
    def evaluaciones_congeladas(run_id: str, episodios_detalle: bool = Query(False, alias="episodios")):
        """Evaluaciones ya hechas (manifiesto y archivo de resultados); no ejecuta nada."""
        manifest = registry.cargar_manifiesto(run_id, raiz) if (raiz / "manifests" / f"{run_id}.json").is_file() else None
        if manifest is None:
            raise ErrorModelo("modelo_no_encontrado", f"No hay manifiesto para '{run_id}'", 404, {"run_id": run_id})
        salida = {"run_id": run_id, "evaluation_suite_id": manifest["evaluation_suite_id"],
                  "manifiesto": manifest.get("evaluation"), "test_final": manifest.get("test_final"),
                  "results_uri": manifest.get("results_uri"), "resultados": None}
        archivo = raiz / (manifest.get("results_uri") or "")
        if manifest.get("results_uri") and archivo.is_file():
            datos = json.loads(archivo.read_text())
            salida["resultados"] = {k: datos.get(k) for k in ("completed", "summary", "blocked_minus_normal", "errors")}
            if episodios_detalle:
                salida["resultados"]["episodes"] = datos.get("episodes")
        return salida

    @app.post("/evaluaciones", status_code=202)
    def evaluar(cuerpo: Evaluar):
        """Evaluación CERTIFICADA, asíncrona: suite fija, catálogo legacy-18, determinista, con `pipelines.evaluate`
        (la misma del flujo). Valida y carga el modelo aquí (errores inmediatos: 400/404/409/500) y encola; el
        resultado se consulta en GET /evaluaciones/trabajos/{id}. PPO usa la política NumPy verificada."""
        from pipelines.baselines import make_policy
        from pipelines.evaluate import evaluate

        datos = suite(cuerpo.suite_id)
        recompensa, sha, npz_sha = None, None, None
        if cuerpo.politica == "ppo":
            run_id = cuerpo.run_id or almacen.servido()["run_id"]
            cargado = almacen.obtener(run_id)  # cadena de hashes manifiesto → ficha → .npz
            layout = cargado.manifiesto.get("layout_path")
            if NIVELES[datos["nivel"]]["layout"] != layout:
                raise ErrorModelo("modelo_incompatible", f"{run_id} usa {layout}; {cuerpo.suite_id} usa otro mapa",
                                  409, {"run_id": run_id, "suite_id": cuerpo.suite_id})
            recompensa = cargado.manifiesto.get("reward_overrides") or None
            sha, npz_sha, politica = cargado.model_sha256, cargado.npz_sha256, cargado.politica
        elif cuerpo.run_id is not None:
            raise ErrorModelo("parametro_invalido", "run_id solo aplica a la política ppo", 400)
        else:
            run_id, layout = None, NIVELES[datos["nivel"]]["layout"]
            politica = make_policy("heuristic") if cuerpo.politica == "heuristic" else None  # random: por semilla
        quien = run_id or cuerpo.politica
        escenario = f"{datos['nivel']}/{'cerrado' if datos['bloqueado'] else 'abierto'}"
        contador = (_ContadorEpisodios(politica, lambda ms: metricas.registrar_decision(quien, ms))
                    if politica is not None else None)

        def tarea() -> dict:
            with tempfile.TemporaryDirectory(prefix="eval-") as tmp:
                # model_path inexistente a propósito: la política va inyectada y evaluate() no debe leer metadatos
                resultado = evaluate(policies=(cuerpo.politica,), orders=_orders(datos["nivel"], raiz),
                                     episodes=datos["episodios"], seed_start=datos["semillas"][0],
                                     scenarios=(datos["bloqueado"],), model_path=Path(tmp) / "politica-inyectada",
                                     layout_path=str(raiz / layout), output_dir=tmp, reward_overrides=recompensa,
                                     policy_objects={cuerpo.politica: contador} if contador else None)
            if resultado["errors"]:
                raise ErrorModelo("evaluacion_fallida", "La evaluación no terminó", 500, {"errores": resultado["errors"]})
            for fila in resultado["episodes"]:
                metricas.registrar_fin(quien, escenario, fila["success"], fila["end_reason"], origen="evaluacion")
            return {"resumen": resultado["summary"][0], "por_episodio": resultado["episodes"]}

        descripcion = {"suite_id": cuerpo.suite_id, "politica": cuerpo.politica, "run_id": run_id,
                       "model_sha256": sha, "npz_sha256": npz_sha,
                       "inferencia": "numpy" if cuerpo.politica == "ppo" else cuerpo.politica,
                       "escenario": escenario, "catalog_version": CATALOGO_SUITES, "certificado": True,
                       "determinista": True, "episodios": datos["episodios"],
                       "semillas": [datos["semillas"][0], datos["semillas"][-1]]}
        return trabajos.encolar(descripcion, tarea, contador)

    @app.get("/evaluaciones/trabajos/{evaluacion_id}")
    def ver_evaluacion(evaluacion_id: str):
        """Estado de una evaluación: en_cola (con posición), en_curso (con progreso), terminada (con resultado)
        o fallida (con error). Caduca a los 30 min sin consultarse una vez terminada."""
        return trabajos.ver(evaluacion_id)

    # --- Episodios -----------------------------------------------------------------------------

    @app.post("/episodios", status_code=201)
    def crear_episodio(cuerpo: CrearEpisodio):
        return episodios.crear(**cuerpo.model_dump())

    @app.get("/episodios/{episodio_id}")
    def ver_episodio(episodio_id: str):
        return episodios.obtener(episodio_id)

    @app.post("/episodios/{episodio_id}/paso")
    def paso(episodio_id: str, cuerpo: Paso | None = None):
        return episodios.paso(episodio_id, cuerpo.accion if cuerpo else None)

    @app.post("/episodios/{episodio_id}/correr")
    def correr(episodio_id: str, cuerpo: Correr | None = None):
        return episodios.correr(episodio_id, cuerpo.max_pasos if cuerpo else None)

    @app.delete("/episodios/{episodio_id}")
    def cerrar(episodio_id: str):
        return episodios.cerrar(episodio_id)

    # --- Escena y monitoreo --------------------------------------------------------------------

    @app.get("/layout")
    def layout(nivel: Literal["m1", "m1b", "m1o"] = Query("m1")):
        """Mapa y catálogo de productos del mismo ambiente que usan los episodios (no el de las suites)."""
        from envs import ENV_VERSION, make_env

        env = make_env(NIVELES[nivel]["bloqueado"], str(raiz / NIVELES[nivel]["layout"]), _orders(nivel, raiz),
                       catalog=CATALOGO_EPISODIOS)
        try:
            return {"nivel": nivel, "layout_path": NIVELES[nivel]["layout"], "layout": env.layout.data,
                    "layout_sha256": env.layout.digest, "bloqueado_por_defecto": NIVELES[nivel]["bloqueado"],
                    "catalog": list(env.inventory.catalog.values()), "catalog_version": env.inventory.catalog_version,
                    "catalogo_evaluaciones": CATALOGO_SUITES, "environment_version": ENV_VERSION}
        finally:
            env.close()

    @app.get("/monitoreo")
    def monitoreo():
        """Monitoreo mínimo del curso: éxito por escenario, causas de fallo, latencia, errores y versión servida."""
        return {"servido": almacen.servido(), "git_commit": commit, "iniciado_en": iniciado,
                "evaluaciones": trabajos.estado(),
                **metricas.resumen(), "http": http.resumen(), "episodios": episodios.estado(),
                "modelos": almacen.estado()}

    return app


app = create_app()
