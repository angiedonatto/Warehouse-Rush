"""Visor Three.js local: los estados proceden exclusivamente de WarehouseRushEnv.

HTTP de biblioteca estándar, una sesión local, sin servicio cloud ni otro motor
de simulación. Las animaciones del navegador interpolan los estados discretos.
"""

from collections import deque
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
from threading import RLock, Timer
from urllib.parse import urlsplit
import webbrowser

from envs.env import Action, WarehouseRushEnv
from pipelines.baselines import make_policy
from envs.missions import MakeupMissionEnv
from envs.inventory import Inventory, CATALOG
from pipelines.train import default_model

WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
EXPERIMENT_MODEL = WEB_ROOT.parent / "models/experiment-001/ppo-orders1-seed42.zip"


def viewer_model(orders):
    """Modelo local reciente o snapshot pequeño e inmutable del experimento 001."""
    local = default_model(orders)
    if local.is_file() or orders != 1:
        return local
    return EXPERIMENT_MODEL


class ViewerSession:
    def __init__(self, layout_path=None, policy_factory=make_policy, settings=None):
        self.lock = RLock()
        self.layout_path = layout_path
        self.policy_factory = policy_factory
        self.env = None
        self.inventory = Inventory()
        self.reset(settings or {"orders": 2, "blocked": True, "policy": "heuristic", "seed": 10000})

    def reset(self, settings):
        with self.lock:
            orders = settings.get("orders", 2)
            blocked = settings.get("blocked", True)
            name = settings.get("policy", "heuristic")
            seed = settings.get("seed", 10000)
            if type(orders) is not int or orders not in (1, 2):
                raise ValueError("orders debe ser 1 o 2")
            if type(blocked) is not bool or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
                raise ValueError("blocked debe ser booleano y seed un entero no negativo de 32 bits")
            if name not in ("heuristic", "random", "ppo", "manual"):
                raise ValueError("Política desconocida")
            # Construir primero: un error de modelo no destruye la sesión vigente.
            policy = None if name == "manual" else self.policy_factory(name, seed, viewer_model(orders))
            makeup = settings.get("makeup", False)
            if type(makeup) is not bool:
                raise ValueError("makeup debe ser booleano")
            env_type = MakeupMissionEnv if makeup else WarehouseRushEnv
            environment = env_type(orders, blocked, self.layout_path, **({"inventory": self.inventory} if makeup else {}))
            observation, info = environment.reset(seed=seed)
            if self.env is not None:
                if isinstance(self.env, MakeupMissionEnv):
                    self.inventory.close(self.env.order_id, time=self.env.state.tiempo)
                self.env.close()
            info = environment._info()  # Refleja también reservas liberadas del pedido anterior.
            self.env, self.observation, self.info = environment, observation, info
            self.policy, self.policy_name = policy, name
            self.seed, self.done = seed, False
            self.terminated = self.truncated = False
            self.last_action, self.last_reward = None, 0.0
            self.trail = [list(environment.position)]
            self.events = [{"step": 0, "kind": "reset", "text": "Misión preparada. Robot en BASE."}]
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
                    "trail": self.trail.copy(), "events": self.events[-8:]}

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
                "available_ppo": {str(order): viewer_model(order).is_file() for order in (1, 2)},
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
