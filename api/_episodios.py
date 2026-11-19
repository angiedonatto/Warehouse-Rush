"""Episodios interactivos de la API: sesiones en memoria con caducidad y métricas de monitoreo.

Un episodio es una simulación `warehouse-v10` (la misma `envs.make_env` que entrenamiento y evaluación; la
simulación Python es la autoridad y la web solo la dibuja). Cada episodio declara su `modo`, como pide el
enunciado: `evaluacion` (PPO del catálogo, determinista), `referencia` (heurística BFS privilegiada),
`aleatoria` o `manual`.

- PPO: mapa, recompensa y nivel salen del manifiesto del modelo (`layout_path`, `reward_overrides`,
  `level_id`); el modelo se obtiene de `AlmacenModelos` (sha256 verificado). Sin `run_id` se usa el modelo
  de producción. Se puede pedir otro nivel con el mismo mapa (p. ej. `m1-c3-seed0` con el paso cerrado
  de `m1b`: la degradación del incidente N3).
- Heurística, aleatoria y manual: mapa del nivel (tabla NIVELES) y recompensa base del ambiente.
- Memoria: caducan a los 30 min sin uso; máximo 200. Si está lleno se descarta el terminado más antiguo; si
  todos siguen activos, 429. Un reinicio del Space los pierde (la web crea uno nuevo).
- `Metricas` (monitoreo mínimo del curso): éxito y causas de fin por modelo/política y escenario, y latencia
  de decisión por paso.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import secrets
import threading
import time

import yaml

from api._modelos import AlmacenModelos, ErrorModelo
from envs import ENV_VERSION, make_env
from envs.env import Action

# Mapa y escenario por nivel (docs/niveles.md). Solo el mapa con muro tiene el paso cerrable (6,14).
NIVELES = {
    "m1": {"layout": "configs/layout_v0.4.json", "bloqueado": False, "cerrable": True},
    "m1b": {"layout": "configs/layout_v0.4.json", "bloqueado": True, "cerrable": True},
    "m1o": {"layout": "configs/layout_v0.5.json", "bloqueado": False, "cerrable": False},
}
MODOS = {"ppo": "evaluacion", "heuristic": "referencia", "random": "aleatoria", "manual": "manual"}
# Catálogo de productos (decisión de lis, 2026-11-18, docs/decisiones.md): los episodios para la web usan el catálogo
# operativo trendy-27-v1; las evaluaciones en suites (POST /evaluaciones → pipelines.evaluate → make_env) siguen con
# legacy-18, con el que se entrenaron y certificaron los modelos. No cambia observación, acciones ni recompensa.
CATALOGO_EPISODIOS = "trendy-27-v1"
CATALOGO_SUITES = "legacy-18"
SEMILLA_MAX = 2**32 - 1
EVENTOS = (("pickup", "Producto cargado"), ("delivery", "Entrega en la cinta"),
           ("collision", "Colisión detectada"), ("invalid_interaction", "Interacción inválida"))


class ErrorEpisodio(ErrorModelo):
    """Mismo formato que ErrorModelo (código estable + estado HTTP); la API maneja ambos igual."""


def _orders(nivel: str, raiz: Path) -> int:
    return int(yaml.safe_load((raiz / "configs/niveles.yaml").read_text())[nivel]["orders"])


# --- Monitoreo -------------------------------------------------------------------------------------

class Metricas:
    """Contadores en memoria (se reinician con el proceso). Seguro entre hilos."""

    def __init__(self, muestras: int = 2000):
        self._lock = threading.Lock()
        self._latencias: dict[str, deque] = {}
        self._muestras = muestras
        self._fines: dict[str, dict] = {}

    def registrar_decision(self, quien: str, ms: float) -> None:
        with self._lock:
            self._latencias.setdefault(quien, deque(maxlen=self._muestras)).append(ms)

    def registrar_fin(self, quien: str, escenario: str, exito: bool, causa: str, origen: str = "episodio") -> None:
        clave = f"{quien}|{escenario}"
        with self._lock:
            r = self._fines.setdefault(clave, {"quien": quien, "escenario": escenario, "episodios": 0,
                                               "exitos": 0, "causas": {}, "origen": {}})
            r["episodios"] += 1
            r["exitos"] += int(bool(exito))
            r["causas"][causa] = r["causas"].get(causa, 0) + 1
            r["origen"][origen] = r["origen"].get(origen, 0) + 1

    def resumen(self) -> dict:
        def percentil(valores, q):
            orden = sorted(valores)
            return round(orden[min(len(orden) - 1, int(q * len(orden)))], 3)

        with self._lock:
            latencia = {q: {"n": len(v), "p50_ms": percentil(v, 0.5), "p95_ms": percentil(v, 0.95),
                            "max_ms": round(max(v), 3)} for q, v in self._latencias.items() if v}
            exito = [{**r, "tasa_exito": round(r["exitos"] / r["episodios"], 4),
                      "causas": dict(r["causas"]), "origen": dict(r["origen"])} for r in self._fines.values()]
        return {"latencia_decision": latencia, "exito_por_escenario": exito}


# --- Episodios -------------------------------------------------------------------------------------

@dataclass
class Episodio:
    id: str
    politica: str
    run_id: str | None
    model_sha256: str | None
    nivel: str
    bloqueado: bool
    seed: int
    layout_path: str
    env: object
    agente: object | None
    observation: object
    info: dict
    ultimo_acceso: float
    creado_en: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    done: bool = False
    terminated: bool = False
    truncated: bool = False
    last_action: dict | None = None
    last_reward: float = 0.0
    trail: list = field(default_factory=list)
    events: list = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def quien(self) -> str:
        return self.run_id or self.politica

    @property
    def escenario(self) -> str:
        return f"{self.nivel}/{'cerrado' if self.bloqueado else 'abierto'}"


class GestorEpisodios:
    def __init__(self, almacen: AlmacenModelos, *, ttl_s: float = 30 * 60, maximo: int = 200,
                 metricas: Metricas | None = None, reloj=time.monotonic):
        self.almacen, self.ttl_s, self.maximo = almacen, ttl_s, maximo
        self.metricas = metricas or Metricas()
        self._reloj = reloj
        self._episodios: dict[str, Episodio] = {}
        self._lock = threading.Lock()

    # --- Ciclo de vida ---------------------------------------------------------------------------

    def crear(self, *, politica: str = "ppo", run_id: str | None = None, nivel: str | None = None,
              bloqueado: bool | None = None, seed: int = 10_000) -> dict:
        from pipelines.baselines import RandomPolicy, make_policy

        if politica not in MODOS:
            raise ErrorEpisodio("parametro_invalido", f"politica debe ser una de {sorted(MODOS)}", 400)
        if type(seed) is not int or not 0 <= seed <= SEMILLA_MAX:
            raise ErrorEpisodio("parametro_invalido", "seed debe ser un entero entre 0 y 2^32 - 1", 400)
        if bloqueado is not None and type(bloqueado) is not bool:
            raise ErrorEpisodio("parametro_invalido", "bloqueado debe ser booleano", 400)
        if run_id is not None and politica != "ppo":
            raise ErrorEpisodio("parametro_invalido", "run_id solo aplica a la política ppo", 400)
        if nivel is not None and nivel not in NIVELES:
            raise ErrorEpisodio("parametro_invalido", f"nivel debe ser uno de {sorted(NIVELES)}", 400)

        recompensa, sha, agente = None, None, None
        if politica == "ppo":
            run_id = run_id or self.almacen.servido()["run_id"]
            cargado = self.almacen.obtener(run_id)  # 404/409/503/500 con su código
            manifest = cargado.manifiesto
            nivel = nivel or manifest["level_id"]
            layout = manifest.get("layout_path")
            if nivel not in NIVELES or NIVELES[nivel]["layout"] != layout:
                raise ErrorEpisodio("modelo_incompatible",
                                    f"{run_id} se entrenó en {layout}; el nivel {nivel} usa otro mapa", 409,
                                    {"run_id": run_id, "layout_modelo": layout, "nivel": nivel})
            recompensa, sha, agente = manifest.get("reward_overrides") or None, cargado.model_sha256, cargado.politica
        else:
            nivel = nivel or "m1"
            layout = NIVELES[nivel]["layout"]
            agente = (make_policy("heuristic") if politica == "heuristic"
                      else RandomPolicy(seed) if politica == "random" else None)
        bloqueado = NIVELES[nivel]["bloqueado"] if bloqueado is None else bloqueado
        if bloqueado and not NIVELES[nivel]["cerrable"]:
            raise ErrorEpisodio("parametro_invalido", f"el mapa del nivel {nivel} no tiene paso cerrable", 400)

        raiz = self.almacen.raiz
        env = make_env(bloqueado, str(raiz / layout), _orders(nivel, raiz), recompensa, catalog=CATALOGO_EPISODIOS)
        observation, info = env.reset(seed=seed)
        episodio = Episodio(id=secrets.token_urlsafe(12), politica=politica, run_id=run_id if politica == "ppo" else None,
                            model_sha256=sha, nivel=nivel, bloqueado=bloqueado, seed=seed, layout_path=layout,
                            env=env, agente=agente, observation=observation, info=info,
                            ultimo_acceso=self._reloj(), trail=[list(env.position)],
                            events=[{"step": 0, "kind": "reset", "text": "Pedido generado. Robot en BASE."}])
        with self._lock:
            self._hacer_lugar()
            self._episodios[episodio.id] = episodio
        return self._payload(episodio)

    def _hacer_lugar(self) -> None:
        """Con el lock tomado: purga caducados y, si sigue lleno, el terminado más antiguo; si no, 429."""
        ahora = self._reloj()
        for id_, ep in list(self._episodios.items()):
            if ahora - ep.ultimo_acceso > self.ttl_s:
                self._quitar(id_)
        if len(self._episodios) < self.maximo:
            return
        terminados = sorted((ep.ultimo_acceso, id_) for id_, ep in self._episodios.items() if ep.done)
        if not terminados:
            raise ErrorEpisodio("demasiados_episodios",
                                f"Hay {self.maximo} episodios activos; intenta de nuevo en unos minutos", 429)
        self._quitar(terminados[0][1])

    def _quitar(self, id_: str) -> None:
        episodio = self._episodios.pop(id_, None)
        if episodio:
            episodio.env.close()

    def _tomar(self, id_: str) -> Episodio:
        with self._lock:
            episodio = self._episodios.get(id_)
            if episodio is None or self._reloj() - episodio.ultimo_acceso > self.ttl_s:
                if episodio:
                    self._quitar(id_)
                raise ErrorEpisodio("episodio_no_encontrado",
                                    "El episodio no existe o caducó (30 min sin uso); crea uno nuevo", 404,
                                    {"episodio_id": id_})
            episodio.ultimo_acceso = self._reloj()
            return episodio

    def obtener(self, id_: str) -> dict:
        episodio = self._tomar(id_)
        with episodio.lock:
            return self._payload(episodio)

    def cerrar(self, id_: str) -> dict:
        self._tomar(id_)
        with self._lock:
            self._quitar(id_)
        return {"episodio_id": id_, "cerrado": True}

    # --- Pasos -----------------------------------------------------------------------------------

    def paso(self, id_: str, accion: int | None = None) -> dict:
        episodio = self._tomar(id_)
        with episodio.lock:
            self._paso(episodio, accion)
            return self._payload(episodio)

    def correr(self, id_: str, max_pasos: int | None = None) -> dict:
        """Avanza con la política hasta terminar (o `max_pasos`) y devuelve la trayectoria para animarla.
        Cada cuadro lleva el estado sin el inventario completo (va en `final`)."""
        episodio = self._tomar(id_)
        if episodio.politica == "manual":
            raise ErrorEpisodio("parametro_invalido", "correr no aplica al modo manual", 400)
        if max_pasos is not None and (type(max_pasos) is not int or max_pasos < 1):
            raise ErrorEpisodio("parametro_invalido", "max_pasos debe ser un entero >= 1", 400)
        cuadros = []
        with episodio.lock:
            while not episodio.done and (max_pasos is None or len(cuadros) < max_pasos):
                self._paso(episodio, None)
                estado = episodio.env.snapshot()
                estado.pop("inventory", None)
                cuadros.append({"paso": episodio.env.state.tiempo, "accion": episodio.last_action,
                                "recompensa": episodio.last_reward, "estado": estado})
            return {"pasos": len(cuadros), "trayectoria": cuadros, "final": self._payload(episodio)}

    def _paso(self, episodio: Episodio, accion: int | None) -> None:
        if episodio.done:
            raise ErrorEpisodio("episodio_terminado", "El episodio terminó; crea uno nuevo", 409,
                                {"episodio_id": episodio.id})
        env = episodio.env
        if episodio.politica == "manual":
            if type(accion) is not int or not env.action_space.contains(accion):
                raise ErrorEpisodio("parametro_invalido",
                                    f"En modo manual envía una acción entera de 0 a {env.action_space.n - 1}", 400)
        else:
            if accion is not None:
                raise ErrorEpisodio("parametro_invalido", "Las acciones explícitas solo valen en modo manual", 400)
            inicio = time.perf_counter()
            accion = int(episodio.agente.action(episodio.observation, env))
            self.metricas.registrar_decision(episodio.quien, (time.perf_counter() - inicio) * 1000)
        episodio.observation, reward, episodio.terminated, episodio.truncated, episodio.info = env.step(accion)
        episodio.done = episodio.terminated or episodio.truncated
        episodio.last_reward = float(reward)
        episodio.last_action = {"code": accion, "name": Action(accion).name}
        posicion = list(env.position)
        if posicion != episodio.trail[-1]:
            episodio.trail.append(posicion)
        componentes = episodio.info["reward_components"]
        for clave, texto in EVENTOS:
            if componentes.get(clave):
                episodio.events.append({"step": env.state.tiempo, "kind": clave, "text": texto})
        if episodio.done:
            episodio.events.append({"step": env.state.tiempo, "kind": "end",
                                    "text": "Pedido completado" if episodio.info["success"] else episodio.info["end_reason"]})
            self.metricas.registrar_fin(episodio.quien, episodio.escenario, episodio.info["success"],
                                        episodio.info["end_reason"])

    # --- Salida ----------------------------------------------------------------------------------

    def _payload(self, episodio: Episodio) -> dict:
        info = {k: v for k, v in episodio.info.items() if k != "state"}  # el estado va una sola vez
        restante = max(0.0, self.ttl_s - (self._reloj() - episodio.ultimo_acceso))
        return {"episodio_id": episodio.id, "modo": MODOS[episodio.politica], "politica": episodio.politica,
                "run_id": episodio.run_id, "model_sha256": episodio.model_sha256, "nivel": episodio.nivel,
                "bloqueado": episodio.bloqueado, "escenario": episodio.escenario, "seed": episodio.seed,
                "environment_version": ENV_VERSION, "catalog_version": episodio.env.inventory.catalog_version,
                "layout_path": episodio.layout_path,
                "done": episodio.done, "terminated": episodio.terminated, "truncated": episodio.truncated,
                "last_action": episodio.last_action, "last_reward": episodio.last_reward,
                "observation": [float(x) for x in episodio.observation], "state": episodio.env.snapshot(),
                "info": info, "trail": [list(p) for p in episodio.trail], "events": episodio.events[-8:],
                "creado_en": episodio.creado_en, "caduca_en_s": round(restante)}

    def estado(self) -> dict:
        with self._lock:
            activos = sum(not ep.done for ep in self._episodios.values())
            return {"episodios": len(self._episodios), "activos": activos, "maximo": self.maximo,
                    "ttl_s": self.ttl_s}
