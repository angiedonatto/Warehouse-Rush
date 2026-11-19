"""Capa de compatibilidad /api/* sobre Render: el visor de la web actual con el motor de la API nueva.

La web (web/src/main.js) llama hoy a /api/layout, /api/state, /api/reset, /api/step y /api/evaluate (el /api de Vercel,
api/_cloud.py + api/_viewer.py). Esta capa reutiliza la lógica de sesión de `ViewerSession` (api/_viewer.py, sin
tocarla) con tres diferencias que exige Render (docs/decisiones.md, 2026-11-18):

- Inferencia con las políticas NumPy verificadas de `AlmacenModelos` (sin torch ni SB3).
- Sesión identificada por un id en la cabecera `X-Sesion`, no por la cookie firmada de Vercel (no sirve entre dominios).
  Las sesiones viven en la memoria del proceso: caducan a los 30 min sin uso (máx. 100) y se pierden al redesplegar
  o dormirse el servidor.
- Modelos y fichas salen de manifests/ y del catálogo de la API, no de configs/modelos_servidos.json (que se retira).

Decisiones del equipo: el modo antiguo sin maquillaje sigue funcionando (el motor lo trae); `state` sin `X-Sesion`
crea una sesión; `layout.models` lista solo los modelos recomendados; «Evaluar» es un diagnóstico NO certificado.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import secrets
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from api._episodios import CATALOGO_EPISODIOS, CATALOGO_SUITES, Metricas, _orders
from api._modelos import AlmacenModelos, ErrorModelo
from api._viewer import ViewerSession
from envs import ENV_VERSION, make_env
from envs.inventory import Inventory
from envs.missions import MakeupMissionEnv
from pipelines.baselines import make_policy

log = logging.getLogger("warehouse.visor")
SEMILLA_MAX = 2**32 - 1
CUERPO_MAX = 4096  # igual que el /api de Vercel
NIVELES_ROTULO = {"m1": "N2 · mapa con muro", "m1b": "N3 · paso (6,14) cerrado", "m1o": "N1 · mapa abierto"}
SESION_DEFECTO = {"makeup": True, "orders": 1}  # lo mismo que crea el /api de Vercel sin cookie
NOTA_DIAGNOSTICO = ("Diagnóstico rápido NO certificado: pocas semillas consecutivas y el catálogo de la web "
                    f"({CATALOGO_EPISODIOS}). La evaluación oficial es POST /evaluaciones (suites fijas, "
                    f"catálogo {CATALOGO_SUITES}).")


class ErrorSesion(ErrorModelo):
    """La sesión no existe o caducó (404) o no hay lugar para otra (429)."""


# --- Fichas de modelo (lo que la web llama `model`) ----------------------------------------------------

class CatalogoVisor:
    """Ficha de cada modelo para la web, armada una vez desde manifests/ y manifests/catalog.json (inmutables dentro de
    la imagen). Mismos campos que hoy recibe la web; `nivel` con el rótulo de docs/niveles.md."""

    def __init__(self, almacen: AlmacenModelos, raiz: Path):
        self.almacen, self.raiz = almacen, Path(raiz)
        self._fichas: dict[str, dict] = {}
        self._lock = threading.Lock()
        try:
            publicado = json.loads((self.raiz / "manifests/catalog.json").read_text())
            self._catalogo = {m["run_id"]: m for m in publicado["modelos"]}
        except (OSError, ValueError, KeyError):
            self._catalogo = {}

    @staticmethod
    def _ppo(bloque: dict | None) -> dict | None:
        datos = (bloque or {}).get("ppo")
        return {k: datos.get(k) for k in ("success_rate", "mean_steps", "mean_collisions")} if datos else None

    def _test_final(self, manifest: dict) -> dict | None:
        tf = manifest.get("test_final")
        if not tf:
            return None
        if tf.get("by_scenario"):
            ppo = {nombre: self._ppo(v) for nombre, v in tf["by_scenario"].items()}
        else:
            ppo = {"abierto": self._ppo({"ppo": (tf.get("policies") or {}).get("ppo")})}
        return {"suite": tf.get("suite"), "episodes": tf.get("episodes"), "met": tf.get("met"),
                "criterion": tf.get("criterion"), "ppo": ppo}

    def resumen(self, run_id: str) -> dict:
        """Ficha del modelo; ErrorModelo 404/409 si no existe o la API no puede ejecutarlo."""
        with self._lock:
            ficha = self._fichas.get(run_id)
        if ficha is not None:
            return ficha
        manifest = self.almacen.manifiesto_servible(run_id)
        entrada = self._catalogo.get(run_id, {})
        evaluacion = manifest.get("evaluation") or {}
        ficha = {
            "id": run_id, "run_id": run_id, "level_id": manifest["level_id"],
            "nivel": NIVELES_ROTULO.get(manifest["level_id"], manifest["level_id"]),
            "estado": entrada.get("estado") or manifest.get("estado", "candidato"),
            "environment_version": manifest["environment_version"], "algorithm": manifest.get("algorithm", "PPO"),
            "model_sha256": manifest["model_sha256"], "manifiesto": f"manifests/{run_id}.json",
            "evaluation_suite_id": manifest["evaluation_suite_id"],
            "evaluacion": {"suite": evaluacion.get("suite"), "episodes": evaluacion.get("episodes"),
                           "ppo": ({k: self._ppo(v) for k, v in evaluacion["by_scenario"].items()}
                                   if evaluacion.get("by_scenario") else self._ppo(evaluacion.get("policies")))},
            "test_final": self._test_final(manifest), "seed": manifest["seed"],
            "orders": _orders(manifest["level_id"], self.raiz),
            "mlflow": {"tracking_uri": manifest.get("mlflow_tracking_uri"), "run_id": manifest.get("mlflow_run_id"),
                       "experiment": manifest.get("mlflow_experiment")},
            "catalogo_evaluacion": CATALOGO_SUITES, "catalogo_web": CATALOGO_EPISODIOS,
        }
        with self._lock:
            self._fichas[run_id] = ficha
        return ficha

    def recomendados(self) -> list[dict]:
        """Fichas de los modelos recomendados que la API puede ejecutar (decisión: solo esos en `layout.models`);
        el de producción primero."""
        servibles = set(self.almacen.servibles())
        actual = self.almacen.servido()["run_id"]
        ids = sorted((r for r, m in self._catalogo.items() if m.get("estado") == "recomendado" and r in servibles),
                     key=lambda r: (r != actual, r))
        return [self.resumen(r) for r in ids]


class Contexto:
    """Lo que comparten las sesiones del visor: modelos, fichas, métricas y la raíz de la imagen."""

    def __init__(self, almacen: AlmacenModelos, raiz: Path, metricas: Metricas):
        self.almacen, self.raiz, self.metricas = almacen, Path(raiz), metricas
        self.catalogo = CatalogoVisor(almacen, raiz)


class PoliticaMedida:
    """Envuelve una política y mide cada decisión para /monitoreo. No cambia la acción."""

    def __init__(self, politica, quien: str, metricas: Metricas):
        self.politica, self.quien, self.metricas = politica, quien, metricas

    def action(self, observation, env) -> int:
        inicio = time.perf_counter()
        accion = self.politica.action(observation, env)
        self.metricas.registrar_decision(self.quien, (time.perf_counter() - inicio) * 1000)
        return accion


# --- Sesión del visor ----------------------------------------------------------------------------------

def _validar_blocked_seed(blocked, seed) -> None:
    if type(blocked) is not bool or type(seed) is not int or not 0 <= seed <= SEMILLA_MAX:
        raise ValueError("blocked debe ser booleano y seed un entero no negativo de 32 bits")


class SesionVisor(ViewerSession):
    """`ViewerSession` con políticas NumPy, fichas del catálogo de la API y un id de sesión.

    Se mantienen sin cambios: el pedido por semilla, el inventario compartido entre pedidos de la misma sesión
    («Generar pedido»), la ruta BFS de referencia, el modo antiguo sin maquillaje y los eventos. Lo que cambia:
    el PPO genérico del experimento 001 ya no existe (solo modelos del catálogo) y `layout_payload` no consulta SB3.
    """

    def __init__(self, ctx: Contexto, settings: dict | None = None):
        self._ctx = ctx
        self.sesion_id: str | None = None
        self._fin_registrado = None
        # ViewerSession.__init__ ya llama a reset(); los atributos de arriba deben existir antes
        super().__init__(policy_factory=self._fabrica_politica, settings=settings or dict(SESION_DEFECTO))

    def _fabrica_politica(self, name, seed, model_path):
        politica = make_policy(name, seed, model_path)
        return PoliticaMedida(politica, name, self._ctx.metricas)

    # --- reset ---
    def reset(self, settings):
        if settings.get("model") is None and settings.get("policy") == "ppo":
            raise ValueError("El PPO genérico (experimento 001) ya no existe: elige un modelo del catálogo (campo model)")
        return super().reset(settings)

    def _reset_served_model(self, model_id, name, blocked, seed):
        """Modelo del catálogo en el MISMO ambiente con que se evaluó: mapa, pedidos y recompensa de su manifiesto,
        catálogo de la web. Si algo no cuadra, la sesión vigente sigue intacta."""
        if name != "ppo":
            raise ValueError("Un modelo servido se ejecuta con la política ppo")
        _validar_blocked_seed(blocked, seed)
        if not isinstance(model_id, str):
            raise ValueError("model debe ser el id de un modelo del catálogo")
        cargado = self._ctx.almacen.obtener(model_id)  # 404 / 409 / 500 con su código
        manifest = cargado.manifiesto
        ficha = self._ctx.catalogo.resumen(model_id)
        environment = make_env(blocked, str(self._ctx.raiz / manifest["layout_path"]), ficha["orders"],
                               manifest.get("reward_overrides") or None, catalog=CATALOGO_EPISODIOS)
        if environment.layout.digest != manifest.get("layout_sha256"):
            environment.close()
            raise ValueError(f"El mapa de {model_id} no coincide con el de su evaluación")
        observation, _ = environment.reset(seed=seed)
        if self.env is not None:
            if isinstance(self.env, MakeupMissionEnv):
                self.env.inventory.close(self.env.order_id, time=self.env.state.tiempo)
            self.env.close()
        self.inventory = environment.inventory
        self.env, self.observation, self.info = environment, observation, environment._info()
        self.policy = PoliticaMedida(cargado.politica, model_id, self._ctx.metricas)
        self.policy_name, self.model_id = "ppo", model_id
        self.seed, self.done = seed, False
        self.terminated = self.truncated = False
        self.last_action, self.last_reward = None, 0.0
        self.trail = [list(environment.position)]
        self.events = [{"step": 0, "kind": "reset", "text": f"Modelo {model_id} cargado. Robot en BASE."}]
        return self.payload()

    # --- estado ---
    def payload(self):
        with self.lock:
            return {"state": self.env.snapshot(), "info": self.info,
                    "observation": self.observation.tolist(), "policy": self.policy_name,
                    "orders": self.env.orders, "makeup": isinstance(self.env, MakeupMissionEnv), "seed": self.seed,
                    "done": self.done, "terminated": self.terminated, "truncated": self.truncated,
                    "last_action": self.last_action, "last_reward": self.last_reward,
                    "route": self.reference_route(), "route_kind": "bfs_reference",
                    "trail": self.trail.copy(), "events": self.events[-8:],
                    "model": self._ctx.catalogo.resumen(self.model_id) if self.model_id else None,
                    "environment_version": ENV_VERSION, "sesion_id": self.sesion_id}

    def step(self, action=None):
        resultado = super().step(action)
        with self.lock:
            if self.done and self._fin_registrado is not self.env:
                self._fin_registrado = self.env
                escenario = f"{'visor' if not self.model_id else self._ctx.catalogo.resumen(self.model_id)['level_id']}/" \
                            f"{'cerrado' if self.env.state.pasillo_bloqueado else 'abierto'}"
                self._ctx.metricas.registrar_fin(self.model_id or self.policy_name, escenario, self.info["success"],
                                                 self.info["end_reason"], origen="visor")
        return resultado

    def layout_payload(self):
        return {"layout": self.env.layout.data, "catalog": list(self.inventory.catalog.values()),
                "catalog_version": self.inventory.catalog_version, "layout_sha256": self.env.layout.digest,
                "available_ppo": {"1": False, "2": False},  # el PPO genérico de warehouse-v1 ya no existe
                "models": self._ctx.catalogo.recomendados(),
                "environment_version": self.env.layout.data["version"]}  # igual que /api/layout de Vercel


# --- Almacén de sesiones -------------------------------------------------------------------------------

class AlmacenSesiones:
    """Sesiones del visor en memoria: caducan a los `ttl_s` sin uso; máximo `maximo` (si se llena se descarta la más
    antigua ya terminada; si todas siguen activas, 429). Un reinicio del servidor las pierde."""

    def __init__(self, ctx: Contexto, *, ttl_s: float = 30 * 60, maximo: int = 100, reloj=time.monotonic):
        self.ctx, self.ttl_s, self.maximo, self._reloj = ctx, ttl_s, maximo, reloj
        self._sesiones: dict[str, tuple[SesionVisor, list]] = {}  # id -> (sesión, [último acceso])
        self._lock = threading.Lock()
        self._defecto: dict | None = None

    def _hacer_lugar(self) -> None:
        """Con el lock tomado."""
        ahora = self._reloj()
        for id_, (_, acceso) in list(self._sesiones.items()):
            if ahora - acceso[0] > self.ttl_s:
                self._quitar(id_)
        if len(self._sesiones) < self.maximo:
            return
        terminadas = sorted((acceso[0], id_) for id_, (s, acceso) in self._sesiones.items() if s.done)
        if not terminadas:
            raise ErrorSesion("demasiadas_sesiones", f"Hay {self.maximo} sesiones activas; intenta de nuevo en unos minutos", 429)
        self._quitar(terminadas[0][1])

    def _quitar(self, id_: str) -> None:
        sesion, _ = self._sesiones.pop(id_)
        sesion.env.close()

    def crear(self, settings: dict | None = None) -> SesionVisor:
        with self._lock:
            self._hacer_lugar()  # falla pronto (429) antes de construir el ambiente
        sesion = SesionVisor(self.ctx, settings)  # ValueError si los ajustes no valen: no se guarda nada
        sesion.sesion_id = secrets.token_urlsafe(12)
        with self._lock:
            self._hacer_lugar()
            self._sesiones[sesion.sesion_id] = (sesion, [self._reloj()])
        return sesion

    def obtener(self, id_: str) -> SesionVisor:
        with self._lock:
            par = self._sesiones.get(id_)
            if par is None or self._reloj() - par[1][0] > self.ttl_s:
                if par is not None:
                    self._quitar(id_)
                raise ErrorSesion("sesion_no_encontrada",
                                  "La sesión no existe o caducó (30 min sin uso, o el servidor se reinició); "
                                  "reinicia la misión", 404, {"sesion_id": id_})
            par[1][0] = self._reloj()
            return par[0]

    def layout_defecto(self) -> dict:
        """/api/layout sin sesión: mapa y catálogo de la sesión por defecto, calculado una vez y sin guardar sesión."""
        with self._lock:
            if self._defecto is not None:
                return self._defecto
        sesion = SesionVisor(self.ctx)
        defecto = sesion.layout_payload()
        sesion.env.close()
        with self._lock:
            self._defecto = defecto
        return defecto

    def estado(self) -> dict:
        with self._lock:
            return {"sesiones": len(self._sesiones), "activas": sum(not s.done for s, _ in self._sesiones.values()),
                    "maximo": self.maximo, "ttl_s": self.ttl_s}


# --- «Evaluar» rápido (diagnóstico NO certificado) -----------------------------------------------------

def evaluar_diagnostico(ctx: Contexto, model_id, blocked=False, episodes=10, seed=10_000) -> dict:
    """Mismo contrato que /api/evaluate de Vercel (modelo congelado, determinista, `episodes` semillas consecutivas desde
    `seed`, ambiente de la web) con la política NumPy, y declarado como NO certificado."""
    if type(blocked) is not bool or type(episodes) is not int or not 1 <= episodes <= 20:
        raise ValueError("blocked debe ser booleano y episodes un entero de 1 a 20")
    if type(seed) is not int or not 0 <= seed <= SEMILLA_MAX - episodes:
        raise ValueError("seed debe ser un entero no negativo de 32 bits")
    if not isinstance(model_id, str):
        raise ValueError("model debe ser el id de un modelo del catálogo")
    cargado = ctx.almacen.obtener(model_id)
    manifest, ficha = cargado.manifiesto, ctx.catalogo.resumen(model_id)
    layout = str(ctx.raiz / manifest["layout_path"])
    escenario = f"{ficha['level_id']}/{'cerrado' if blocked else 'abierto'}"
    filas, latencias, errores = [], [], 0
    for semilla in range(seed, seed + episodes):
        env = make_env(blocked, layout, ficha["orders"], manifest.get("reward_overrides") or None,
                       catalog=CATALOGO_EPISODIOS)
        observation, _ = env.reset(seed=semilla)
        hecho, total = False, 0.0
        try:
            while not hecho:
                inicio = time.perf_counter()
                accion = cargado.politica.action(observation, env)
                ms = (time.perf_counter() - inicio) * 1000
                latencias.append(ms)
                ctx.metricas.registrar_decision(model_id, ms)
                observation, recompensa, terminado, truncado, info = env.step(accion)
                total += recompensa
                hecho = terminado or truncado
            filas.append({"seed": semilla, "success": bool(info["success"]), "steps": env.state.tiempo,
                          "collisions": env.state.colisiones, "deliveries": env.state.entregas,
                          "reward": round(total, 3), "end_reason": info["end_reason"]})
            ctx.metricas.registrar_fin(model_id, escenario, info["success"], info["end_reason"], origen="diagnostico")
        except Exception as exc:  # se cuenta como error de inferencia, no se oculta
            errores += 1
            filas.append({"seed": semilla, "success": False, "error": f"{type(exc).__name__}: {exc}"[:200]})
        finally:
            env.close()
    exitos = [f for f in filas if f["success"]]
    causas: dict[str, int] = {}
    for f in filas:
        causas[f.get("end_reason", "error")] = causas.get(f.get("end_reason", "error"), 0) + 1
    latencias.sort()
    return {"mode": "evaluation", "certificado": False, "nota": NOTA_DIAGNOSTICO, "model": ficha,
            "environment_version": ENV_VERSION, "catalog": CATALOGO_EPISODIOS,
            "scenario": "cerrado" if blocked else "abierto", "seeds": [seed, seed + episodes - 1], "episodes": filas,
            "summary": {"success_rate": len(exitos) / episodes,
                        "mean_steps_success": round(sum(f["steps"] for f in exitos) / len(exitos), 1) if exitos else None,
                        "mean_collisions": round(sum(f.get("collisions", 0) for f in filas) / episodes, 2),
                        "end_reasons": causas},
            "monitoring": {"inference_ms_mean": round(sum(latencias) / len(latencias), 3) if latencias else None,
                           "inference_ms_p95": round(latencias[int(0.95 * (len(latencias) - 1))], 3) if latencias else None,
                           "steps": len(latencias), "errors": errores, "served_sha256": cargado.model_sha256,
                           "inferencia": "numpy"}}


# --- Router /api/* (mismas rutas y formatos que usa la web) ---------------------------------------------

class ErrorPeticion(Exception):
    """Petición mal formada (415 u otro): se responde en el formato de error de /api/*."""

    def __init__(self, estado: int, texto: str, codigo: str):
        super().__init__(texto)
        self.estado, self.texto, self.codigo = estado, texto, codigo


def _error(estado: int, texto: str, codigo: str, detalle: dict | None = None) -> JSONResponse:
    """Formato de error del /api de Vercel: {"error": "texto"} (la web hace `new Error(result.error)`), más un
    `codigo` estable. Los demás endpoints de la API usan {"error": {"codigo", "mensaje", "detalle"}}."""
    cuerpo = {"error": texto, "codigo": codigo}
    if detalle:
        cuerpo["detalle"] = detalle
    return JSONResponse(cuerpo, estado)


async def _leer_cuerpo(request: Request) -> dict:
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise ErrorPeticion(415, "Se requiere application/json", "tipo_no_soportado")
    crudo = await request.body()
    if not 0 < len(crudo) <= CUERPO_MAX:
        raise ValueError("Cuerpo JSON inválido")
    cuerpo = json.loads(crudo)
    if not isinstance(cuerpo, dict):
        raise ValueError("Se requiere un objeto JSON")
    return cuerpo


class Visor:
    """Contexto, sesiones y operaciones de /api/*; `montar_visor` las expone como rutas."""

    def __init__(self, almacen: AlmacenModelos, raiz: Path, metricas: Metricas, commit: str, servido_fijo):
        self.ctx = Contexto(almacen, raiz, metricas)
        self.sesiones = AlmacenSesiones(self.ctx)
        self.commit, self.servido_fijo = commit, servido_fijo
        self._diagnostico = threading.Semaphore(1)  # «Evaluar» rápido: uno a la vez (0.1 CPU en Render Free)

    def health(self, _cuerpo, _id) -> dict:
        servido = self.servido_fijo()
        return {"status": "ok", "environment_version": ENV_VERSION,
                "served_models": [{"id": m["id"], "estado": m["estado"], "model_sha256": m["model_sha256"]}
                                  for m in self.ctx.catalogo.recomendados()],
                "servido": servido["run_id"], "session_mode": "id en la cabecera X-Sesion (memoria del servidor)",
                "commit": self.commit, **self.sesiones.estado()}

    def layout(self, _cuerpo, id_) -> dict:
        if id_:
            try:
                return self.sesiones.obtener(id_).layout_payload()
            except ErrorSesion:
                pass  # como en Vercel: sin sesión válida se muestra el mapa por defecto
        return self.sesiones.layout_defecto()

    def state(self, _cuerpo, id_) -> dict:
        sesion = self.sesiones.obtener(id_) if id_ else self.sesiones.crear()  # decisión: sin id crea una sesión
        return sesion.payload()

    def reset(self, cuerpo, id_) -> dict:
        try:
            sesion = self.sesiones.obtener(id_) if id_ else None
        except ErrorSesion:
            sesion = None  # id desconocido o caducado: reset es la forma de recuperarse; se crea una sesión nueva
        if sesion is None:
            return self.sesiones.crear(cuerpo).payload()
        return sesion.reset(cuerpo)

    def step(self, cuerpo, id_) -> dict:
        if not id_:
            raise ErrorPeticion(400, "Falta la cabecera X-Sesion: llama primero a /api/state o /api/reset", "falta_sesion")
        return self.sesiones.obtener(id_).step(cuerpo.get("action"))

    def evaluate(self, cuerpo, _id) -> dict:
        if not self._diagnostico.acquire(blocking=False):
            raise ErrorSesion("diagnostico_en_curso", "Ya hay un diagnóstico en curso; reintenta en unos segundos", 429)
        try:
            return evaluar_diagnostico(self.ctx, cuerpo.get("model"), cuerpo.get("blocked", False),
                                       cuerpo.get("episodes", 10), cuerpo.get("seed", 10_000))
        finally:
            self._diagnostico.release()


async def _servir(request: Request, operacion, con_cuerpo: bool = False) -> JSONResponse:
    """Ejecuta una operación del visor (en un hilo: es CPU) y traduce sus errores al formato de /api/*."""
    try:
        cuerpo = await _leer_cuerpo(request) if con_cuerpo else None
        resultado = await run_in_threadpool(operacion, cuerpo, request.headers.get("x-sesion") or None)
    except ErrorPeticion as exc:
        return _error(exc.estado, exc.texto, exc.codigo)
    except ErrorModelo as exc:  # también ErrorSesion
        return _error(exc.estado_http, exc.mensaje, exc.codigo, exc.detalle)
    except (ValueError, FileNotFoundError) as exc:
        return _error(400, str(exc), "parametro_invalido")
    except LookupError as exc:
        return _error(404, str(exc), "no_encontrado")
    except Exception as exc:
        log.exception("Error en /api/*")
        return _error(500, f"{type(exc).__name__}: {exc}"[:300], "error_interno")
    id_sesion = resultado.get("sesion_id") if isinstance(resultado, dict) else None
    return JSONResponse(resultado, headers={"X-Sesion": id_sesion} if id_sesion else None)


def montar_visor(app, *, almacen: AlmacenModelos, raiz: Path, metricas: Metricas, commit: str, servido_fijo) -> Visor:
    """Agrega las rutas /api/health, /layout, /state, /reset, /step y /evaluate a `app` y devuelve el `Visor`."""
    visor = Visor(almacen, Path(raiz), metricas, commit, servido_fijo)
    router = APIRouter(prefix="/api", tags=["visor (compatibilidad con la web actual)"])

    @router.get("/health")
    async def health(request: Request):
        return await _servir(request, visor.health)

    @router.get("/layout")
    async def layout(request: Request):
        return await _servir(request, visor.layout)

    @router.get("/state")
    async def state(request: Request):
        return await _servir(request, visor.state)

    @router.post("/reset")
    async def reset(request: Request):
        return await _servir(request, visor.reset, con_cuerpo=True)

    @router.post("/step")
    async def step(request: Request):
        return await _servir(request, visor.step, con_cuerpo=True)

    @router.post("/evaluate")
    async def evaluate(request: Request):
        return await _servir(request, visor.evaluate, con_cuerpo=True)

    @router.api_route("/{ruta:path}", methods=["GET", "POST"], include_in_schema=False)
    async def desconocida(ruta: str):
        return _error(404, "Ruta desconocida", "ruta_no_encontrada")

    app.include_router(router)
    return visor
