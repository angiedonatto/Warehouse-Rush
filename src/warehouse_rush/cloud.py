"""Adaptador HTTP stateless: snapshot firmado por visitante, sin alterar el entorno.

La cookie sólo conserva una simulación académica, no identidad ni clasificación.
El servidor verifica su firma antes de restaurarla y ejecuta el mismo env.step().
"""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import asdict
from functools import lru_cache, partial
from hashlib import sha256
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import time
import zlib
from urllib.parse import parse_qs, urlsplit

from warehouse_rush.env import WorldState
from warehouse_rush.missions import MakeupMissionEnv
from warehouse_rush.inventory import Inventory
from warehouse_rush.policies import make_policy
from warehouse_rush.viewer import ViewerSession, WEB_ROOT

COOKIE_NAME = "warehouse_session"
MAX_AGE = 7200


@lru_cache(maxsize=2)
def cached_ppo(model_path):
    return make_policy("ppo", model_path=model_path)


def cloud_policy(name, seed, model_path):
    return cached_ppo(str(model_path)) if name == "ppo" else make_policy(name, seed, model_path)


class SignedSessions:
    def __init__(self, secret):
        if not secret or len(secret) < 32:
            raise RuntimeError("WAREHOUSE_SESSION_SECRET debe tener al menos 32 caracteres")
        self.key = secret.encode()

    def dump(self, session):
        record = {
            "v": 1, "expires": int(time.time()) + MAX_AGE,
            "orders": session.env.orders, "policy": session.policy_name, "seed": session.seed,
            "state": asdict(session.env.state), "picked": sorted(session.env.picked_packages),
            "completed": sorted(session.env.completed_packages), "done": session.done,
            "terminated": session.terminated, "truncated": session.truncated,
            "reason": session.info["end_reason"], "components": session.info["reward_components"],
            "last_action": session.last_action, "last_reward": session.last_reward,
            "trail": session.trail[-64:], "events": session.events[-8:],
        }
        if isinstance(session.env, MakeupMissionEnv):
            record['makeup'] = True
            record['inventory'] = dict(initial=session.inventory.initial, total=session.inventory.total, orders=session.inventory.orders)
            record['order_id'] = session.env.order_id
            record['orders'] = 1  # Parámetro legacy constructor; líneas se restauran aparte.
        raw = json.dumps(record, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        encoded = urlsafe_b64encode(zlib.compress(raw) if record.get("makeup") else raw).decode().rstrip("=")
        signature = hmac.new(self.key, encoded.encode(), sha256).hexdigest()
        token = f"{encoded}.{signature}"
        if len(token) > 3800:
            raise RuntimeError("El snapshot excede el tamaño de cookie permitido")
        return token

    def load(self, token):
        if not token:
            return ViewerSession(policy_factory=cloud_policy)
        if len(token) > 3800 or "." not in token:
            raise ValueError("Sesión inválida; reinicia la misión")
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(self.key, encoded.encode(), sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Firma de sesión inválida; reinicia la misión")
        try:
            raw = urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            if not raw.startswith(b'{'):
                raw = zlib.decompress(raw)
            record = json.loads(raw)
            if record["v"] != 1 or record["expires"] < time.time():
                raise ValueError("Sesión expirada; reinicia la misión")
            session = ViewerSession(policy_factory=cloud_policy,
                                    settings={"orders": record["orders"], "blocked": record["state"]["pasillo_bloqueado"],
                                              "policy": record["policy"], "seed": record["seed"], "makeup": record.get("makeup", False)})
            if record.get('makeup'):
                saved = record['inventory']
                inventory = Inventory(saved['initial'])
                inventory.total, inventory.orders = saved['total'], saved['orders']
                inventory.check()
                session.inventory = session.env.inventory = inventory
                session.env.order_id = record['order_id']
                session.env.lines = inventory.orders[record['order_id']]['lines']
                session.env.orders = len(session.env.lines)
                session.env.packages = tuple(l['sku'] for l in session.env.lines)
            session.env.state = WorldState(**record["state"])
            session.env.picked_packages = set(record["picked"])
            session.env.completed_packages = set(record["completed"])
            session.env._done = session.done = record["done"]
            session.terminated, session.truncated = record["terminated"], record["truncated"]
            session.env._reason = record["reason"]
            session.observation = session.env._observation()
            session.info = session.env._info(record["components"])
            session.last_action, session.last_reward = record["last_action"], record["last_reward"]
            session.trail, session.events = record["trail"], record["events"]
            if session.policy_name == "random":
                # Random elige una acción por segundo. Restituir la misma secuencia.
                session.policy.rng.integers(5, size=session.env.state.tiempo)
            return session
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Snapshot inválido; reinicia la misión") from exc


class CloudAPI:
    def __init__(self, secret):
        self.sessions = SignedSessions(secret)

    def handle(self, method, endpoint, body=None, token=None):
        if method == "GET" and endpoint == "health":
            return {"status": "ok", "experiment": "001", "environment_version": "0.1.0",
                    "session_mode": "signed-per-visitor",
                    "commit": os.getenv("VERCEL_GIT_COMMIT_SHA", "local")}, None
        if method == "GET" and endpoint == "layout":
            return ViewerSession(policy_factory=cloud_policy).layout_payload(), None
        if method == "GET" and endpoint == "state":
            try:
                session = self.sessions.load(token)
                if token:
                    # Una lectura no debe sobrescribir la cookie de un POST
                    # concurrente con una versión anterior de la misión.
                    return session.payload(), None
            except ValueError:
                session = self.sessions.load(None)
        elif method == "POST" and endpoint == "reset":
            if token:
                try:
                    session = self.sessions.load(token)
                except ValueError:
                    session = ViewerSession(policy_factory=cloud_policy)
                session.reset(body or {})
            else:
                session = ViewerSession(policy_factory=cloud_policy, settings=body or {})
        elif method == "POST" and endpoint == "step":
            session = self.sessions.load(token)
            session.step((body or {}).get("action"))
        else:
            raise LookupError("Ruta desconocida")
        return session.payload(), self.sessions.dump(session)


class CloudHandler(BaseHTTPRequestHandler):
    def _respond(self, data, status=200, token=None):
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if token:
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            self.send_header("Set-Cookie", f"{COOKIE_NAME}={token}; Path=/api; Max-Age={MAX_AGE}; HttpOnly; SameSite=Lax{secure}")
        self.end_headers()
        self.wfile.write(raw)

    def _dispatch(self):
        parsed = urlsplit(self.path)
        endpoint = parse_qs(parsed.query).get("route", [parsed.path.removeprefix("/api/")])[0]
        if endpoint not in ("health", "layout", "state", "reset", "step"):
            return self._respond({"error": "Ruta desconocida"}, 404)
        try:
            body = None
            if self.command == "POST":
                origin = self.headers.get("Origin")
                if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                    return self._respond({"error": "Origen no permitido"}, 403)
                if self.headers.get_content_type() != "application/json":
                    return self._respond({"error": "Se requiere application/json"}, 415)
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 4096:
                    raise ValueError("Cuerpo JSON inválido")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Se requiere un objeto JSON")
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            token = cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else None
            result, token = CloudAPI(os.environ.get("WAREHOUSE_SESSION_SECRET")).handle(self.command, endpoint, body, token)
            self._respond(result, token=token)
        except (ValueError, FileNotFoundError) as exc:
            self._respond({"error": str(exc)}, 400)
        except LookupError as exc:
            self._respond({"error": str(exc)}, 404)
        except Exception as exc:
            logging.exception("Error real en API del experimento 001")
            self._respond({"error": f"{type(exc).__name__}: {exc}"}, 500)

    do_GET = do_POST = _dispatch


def preview(port=8090):
    """Probar localmente exactamente el handler desplegado y sus cookies."""
    import secrets

    os.environ.setdefault("WAREHOUSE_SESSION_SECRET", secrets.token_urlsafe(48))

    class PreviewHandler(CloudHandler, SimpleHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path.startswith("/api/"):
                self._dispatch()
            else:
                SimpleHTTPRequestHandler.do_GET(self)

    server = ThreadingHTTPServer(("127.0.0.1", port), partial(PreviewHandler, directory=str(WEB_ROOT / "dist")))
    print(f"Preview stateless: http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    preview()
