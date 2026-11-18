"""Visor Three.js local: los estados proceden exclusivamente de WarehouseRushEnv.

HTTP de biblioteca estándar, una sesión local, sin servicio cloud ni otro motor
de simulación. Las animaciones del navegador interpolan los estados discretos.
"""

from collections import deque
from functools import lru_cache, partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from threading import RLock, Timer
from urllib.parse import urlsplit
import webbrowser

from envs import ENV_VERSION, make_env
from envs.env import Action, WarehouseRushEnv
from pipelines.baselines import make_policy
from envs.missions import MakeupMissionEnv
from envs.inventory import Inventory, CATALOG
from pipelines.train import default_model

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
EXPERIMENT_MODEL = WEB_ROOT.parent / "models/experiment-001/ppo-orders1-seed42.zip"
SERVED_MODELS = WEB_ROOT.parent / "configs/modelos_servidos.json"   # lo escribe pipelines/servir.py


def viewer_model(orders):
    """Modelo local reciente o snapshot pequeño e inmutable del experimento 001."""
    local = default_model(orders)
    if local.is_file() or orders != 1:
        return local
    return EXPERIMENT_MODEL


@lru_cache(maxsize=8)
def _model_obs_shape(path: str):
    from stable_baselines3 import PPO

    return tuple(PPO.load(path, device="cpu").observation_space.shape)


@lru_cache(maxsize=1)
def served_models() -> dict:
    """Modelos recomendados que la API puede ejecutar, por id (ver pipelines/servir.py)."""
    if not SERVED_MODELS.is_file():
        return {}
    data = json.loads(SERVED_MODELS.read_text())
    return {spec["id"]: spec for spec in data["modelos"] if spec["environment_version"] == ENV_VERSION}


@lru_cache(maxsize=8)
def _verified_model_path(model_id: str) -> Path:
    """Ruta del peso servido tras comprobar su SHA-256 contra el manifiesto (una vez por proceso)."""
    from pipelines.tracking import sha256_file

    spec = served_models().get(model_id)
    if spec is None:
        raise ValueError(f"Modelo desconocido o incompatible con {ENV_VERSION}: {model_id}")
    path = WEB_ROOT.parent / spec["archivo"]
    if not path.is_file() or sha256_file(path) != spec["model_sha256"]:
        raise ValueError(f"El peso servido de {model_id} no coincide con su manifiesto")
    return path


def model_summary(model_id):
    """Identidad que muestra la web: modelo, nivel, estado, ambiente, hash y referencias."""
    if model_id is None:
        return None
    spec = served_models()[model_id]
    keys = ("id", "run_id", "level_id", "nivel", "estado", "environment_version", "algorithm", "model_sha256",
            "manifiesto", "evaluation_suite_id", "evaluacion", "test_final", "mlflow", "orders")
    return {key: spec[key] for key in keys}


def ppo_compatible(orders, layout_path=None) -> bool:
    """El PPO guardado sólo se ofrece si sus observaciones coinciden con las del ambiente vigente
    (p. ej. experiment-001 tiene 22 y warehouse-v10 27): un modelo de otra familia no se sirve."""
    path = viewer_model(orders)
    if not path.is_file():
        return False
    env = WarehouseRushEnv(orders, True, layout_path)
    try:
        return _model_obs_shape(str(path)) == tuple(env.observation_space.shape)
    finally:
        env.close()


class ViewerSession:
    def __init__(self, layout_path=None, policy_factory=make_policy, settings=None):
        self.lock = RLock()
        self.layout_path = layout_path
        self.policy_factory = policy_factory
        self.env = None
        self.inventory = Inventory()
        self.model_id = None
        self.reset(settings or {"orders": 2, "blocked": True, "policy": "heuristic", "seed": 10000})

    def reset(self, settings):
        with self.lock:
            orders = settings.get("orders", 2)
            blocked = settings.get("blocked", True)
            name = settings.get("policy", "heuristic")
            seed = settings.get("seed", 10000)
            model_id = settings.get("model")
            if model_id is not None:
                return self._reset_served_model(model_id, name, blocked, seed)
            if type(orders) is not int or orders not in (1, 2):
                raise ValueError("orders debe ser 1 o 2")
            if type(blocked) is not bool or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
                raise ValueError("blocked debe ser booleano y seed un entero no negativo de 32 bits")
            if name not in ("heuristic", "random", "ppo", "manual"):
                raise ValueError("Política desconocida")
            if name == "ppo" and viewer_model(orders).is_file() and not ppo_compatible(orders, self.layout_path):
                raise ValueError("No hay modelo PPO compatible con el ambiente vigente para esta misión")
            # Construir primero: un error de modelo no destruye la sesión vigente.
            policy = None if name == "manual" else self.policy_factory(name, seed, viewer_model(orders))
            makeup = settings.get("makeup", False)
            if type(makeup) is not bool:
                raise ValueError("makeup debe ser booleano")
            env_type = MakeupMissionEnv if makeup else WarehouseRushEnv
            # Un modelo servido trae su propio inventario (stock repuesto por episodio): al volver a la
            # misión del visor se empieza con el inventario compartido nuevo.
            inventory = Inventory() if self.model_id is not None else self.inventory
            environment = env_type(orders, blocked, self.layout_path, **({"inventory": inventory} if makeup else {}))
            observation, info = environment.reset(seed=seed)
            if self.env is not None:
                if isinstance(self.env, MakeupMissionEnv):
                    self.env.inventory.close(self.env.order_id, time=self.env.state.tiempo)
                self.env.close()
            self.inventory = inventory
            info = environment._info()  # Refleja también reservas liberadas del pedido anterior.
            self.env, self.observation, self.info = environment, observation, info
            self.policy, self.policy_name = policy, name
            self.model_id = None
            self.seed, self.done = seed, False
            self.terminated = self.truncated = False
            self.last_action, self.last_reward = None, 0.0
            self.trail = [list(environment.position)]
            self.events = [{"step": 0, "kind": "reset", "text": "Misión preparada. Robot en BASE."}]
            return self.payload()

    def _reset_served_model(self, model_id, name, blocked, seed):
        """Modelo recomendado en el MISMO ambiente con que se evaluó: mapa, pedidos (N productos de
        1 unidad, stock repuesto) y recompensa de su manifiesto. Si algo no cuadra, la sesión vigente sigue."""
        if name != "ppo":
            raise ValueError("Un modelo servido se ejecuta con la política ppo")
        if type(blocked) is not bool or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise ValueError("blocked debe ser booleano y seed un entero no negativo de 32 bits")
        path = _verified_model_path(model_id)
        spec = served_models()[model_id]
        policy = self.policy_factory("ppo", seed, path)
        environment = make_env(blocked, WEB_ROOT.parent / spec["layout_path"], spec["orders"],
                               spec["reward_overrides"] or None)
        if environment.layout.digest != spec["layout_sha256"]:
            raise ValueError(f"El mapa de {model_id} no coincide con el de su evaluación")
        observation, info = environment.reset(seed=seed)
        if self.env is not None:
            if isinstance(self.env, MakeupMissionEnv):
                self.env.inventory.close(self.env.order_id, time=self.env.state.tiempo)
            self.env.close()
        self.inventory = environment.inventory
        self.env, self.observation, self.info = environment, observation, environment._info()
        self.policy, self.policy_name, self.model_id = policy, "ppo", model_id
        self.seed, self.done = seed, False
        self.terminated = self.truncated = False
        self.last_action, self.last_reward = None, 0.0
        self.trail = [list(environment.position)]
        self.events = [{"step": 0, "kind": "reset", "text": f"Modelo {model_id} cargado. Robot en BASE."}]
        return self.payload()

    def reference_route(self):
        """BFS sólo para la capa visual: no se proporciona al agente PPO."""
        if self.done or self.env.state.objetivo is None:
            return []
        env = self.env
        goals = env.layout.approaches(env.state.objetivo, env.state.pasillo_bloqueado)
        start = env.position
        parents = {start: None}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            if cell in goals:
                route = []
                while cell is not None:
                    route.append(list(cell))
                    cell = parents[cell]
                return route[::-1]
            for neighbor in env.layout.neighbors(cell, env.state.pasillo_bloqueado):
                if neighbor not in parents:
                    parents[neighbor] = cell
                    queue.append(neighbor)
        return []

    def payload(self):
        with self.lock:
            return {"state": self.env.snapshot(), "info": self.info,
                    "observation": self.observation.tolist(), "policy": self.policy_name,
                    "orders": self.env.orders, "makeup": isinstance(self.env, MakeupMissionEnv), "seed": self.seed, "done": self.done,
                    "terminated": self.terminated, "truncated": self.truncated,
                    "last_action": self.last_action, "last_reward": self.last_reward,
                    "route": self.reference_route(), "route_kind": "bfs_reference",
                    "trail": self.trail.copy(), "events": self.events[-8:],
                    "model": model_summary(self.model_id), "environment_version": ENV_VERSION}

    def step(self, action=None):
        with self.lock:
            if self.done:
                raise ValueError("El episodio terminó. Reinicia para volver a ejecutar.")
            if action is None:
                if self.policy is None:
                    raise ValueError("En modo manual selecciona una acción")
                action = self.policy.action(self.observation, self.env)
            elif self.policy_name != "manual":
                raise ValueError("Las acciones explícitas requieren política manual")
            if type(action) is not int or not self.env.action_space.contains(action):
                raise ValueError("Acción inválida: usa un entero de 0 a 4")
            self.observation, self.last_reward, self.terminated, self.truncated, self.info = self.env.step(action)
            self.done = self.terminated or self.truncated
            self.last_action = {"code": action, "name": Action(action).name}
            position = list(self.env.position)
            if position != self.trail[-1]:
                self.trail.append(position)
            components = self.info["reward_components"]
            for key, text in (("pickup", "Paquete recogido"), ("delivery", "Paquete entregado"),
                              ("collision", "Colisión detectada"), ("invalid_interaction", "Interacción inválida")):
                if components[key]:
                    self.events.append({"step": self.env.state.tiempo, "kind": key, "text": text})
            if self.done:
                self.events.append({"step": self.env.state.tiempo, "kind": "end",
                                    "text": "Misión completada" if self.info["success"] else self.info["end_reason"]})
            return self.payload()

    def layout_payload(self):
        return {"layout": self.env.layout.data, "catalog": list(CATALOG.values()), "layout_sha256": self.env.layout.digest,
                "available_ppo": {str(order): ppo_compatible(order, self.layout_path) for order in (1, 2)},
                "models": [model_summary(model_id) for model_id in served_models()],
                "environment_version": self.env.layout.data["version"]}


class ViewerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, session, **kwargs):
        self.session = session
        super().__init__(*args, **kwargs)

    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/layout":
            self.json_response(self.session.layout_payload())
        elif path == "/api/state":
            self.json_response(self.session.payload())
        elif path.startswith("/api/"):
            self.json_response({"error": "Ruta desconocida"}, 404)
        else:
            super().do_GET()

    def do_POST(self):
        # Sólo JSON y origen local; el servidor se enlaza exclusivamente a loopback.
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
            return self.json_response({"error": "Origen no permitido"}, 403)
        if self.headers.get_content_type() != "application/json":
            return self.json_response({"error": "Se requiere application/json"}, 415)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 4096:
                raise ValueError("Cuerpo JSON vacío o demasiado grande")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Se requiere un objeto JSON")
            path = urlsplit(self.path).path
            if path == "/api/reset":
                result = self.session.reset(body)
            elif path == "/api/step":
                result = self.session.step(body.get("action"))
            else:
                return self.json_response({"error": "Ruta desconocida"}, 404)
            self.json_response(result)
        except (ValueError, FileNotFoundError) as exc:
            self.json_response({"error": str(exc)}, 400)
        except Exception as exc:
            self.log_error("Error real del simulador: %s: %s", type(exc).__name__, exc)
            self.json_response({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def log_message(self, fmt, *args):
        # Mantener errores visibles sin imprimir cada frame de telemetría.
        if args and str(args[1] if len(args) > 1 else "").startswith(("4", "5")):
            super().log_message(fmt, *args)


def serve_viewer(port=8080, open_browser=True, layout_path=None):
    if not 1 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 1 y 65535")
    if not (WEB_ROOT / "dist/index.html").is_file():
        print("Preparando interfaz Three.js…", flush=True)
        if not (WEB_ROOT / "node_modules").is_dir():
            subprocess.run(["npm", "ci"], cwd=WEB_ROOT, check=True)
        subprocess.run(["npm", "run", "build"], cwd=WEB_ROOT, check=True)
    session = ViewerSession(layout_path, settings={"orders": 1, "blocked": True, "policy": "heuristic", "makeup": True})
    handler = partial(ViewerHandler, session=session, directory=str(WEB_ROOT / "dist"))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Warehouse Rush 3D → {url}\nCtrl+C para detener el visor.", flush=True)
    if open_browser:
        Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nVisor detenido.")
    finally:
        server.server_close()
        session.env.close()
