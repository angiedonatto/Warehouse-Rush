"""Entorno Gymnasium: estado, movimiento e interacción separados."""

from dataclasses import asdict, dataclass
from enum import IntEnum
import math

import gymnasium as gym
from gymnasium import spaces
import numpy as np

from envs.layout import DIRECTIONS, RAYS, Layout
from envs.rewards import RewardConfig, reward_components


class Action(IntEnum):
    AVANZAR = 0
    GIRAR_IZQUIERDA = 1
    GIRAR_DERECHA = 2
    FRENAR = 3
    CARGAR = 4
    DESCARGAR = 5
    SUBIR = 6
    BAJAR = 7


@dataclass(frozen=True)
class SimulationConfig:
    battery_capacity: float = 100.0
    max_steps: int = 250
    forward_cost: float = 0.8
    turn_cost: float = 0.2
    brake_cost: float = 0.1
    interact_cost: float = 0.2
    step_seconds: float = 1.0
    interaction_radius: int = 1
    sensor_range: int = 8

    def __post_init__(self):
        if self.battery_capacity <= 0 or self.max_steps < 1 or self.sensor_range < 1:
            raise ValueError("Batería, pasos y alcance deben ser positivos")
        if self.step_seconds != 1.0 or self.interaction_radius != 1:
            raise ValueError("v0.1 usa pasos de 1 s y radio de interacción de 1 m")
        if min(self.forward_cost, self.turn_cost, self.brake_cost, self.interact_cost) <= 0:
            raise ValueError("Cada acción debe consumir batería positiva")


@dataclass
class WorldState:
    x: int
    y: int
    theta: int
    v: float
    bateria: float
    carga: str | None
    pedido_actual: int
    etapa: str
    objetivo: str | None
    tiempo: int
    tiempo_restante: int
    entregas: int
    colisiones: int
    interacciones_invalidas: int
    pasillo_bloqueado: bool
    distancia: float = 0.0
    recompensa_total: float = 0.0


class WarehouseRushEnv(gym.Env):
    metadata = {"render_modes": ["ansi", "human"], "render_fps": 5}
    OBSERVATION_SIZE = 27

    def __init__(self, orders: int = 1, blocked: bool = False, layout_path=None,
                 simulation: SimulationConfig | None = None,
                 rewards: RewardConfig | None = None, render_mode: str | None = None):
        super().__init__()
        if orders not in (1, 2):
            raise ValueError("orders debe ser 1 o 2")
        if render_mode not in (None, "ansi", "human"):
            raise ValueError("render_mode debe ser ansi, human o None")
        self.layout = Layout.load(layout_path)
        self.layout.validate_routes()
        self.config = simulation or SimulationConfig(**self.layout.data["simulation"])
        self.reward_config = rewards or RewardConfig(**self.layout.data["rewards"])
        self.orders = orders
        self.packages = ("P1", "P2")[:orders]
        self.blocked = blocked
        self.render_mode = render_mode
        self.action_space = spaces.Discrete(8)
        low = np.zeros(self.OBSERVATION_SIZE, dtype=np.float32)
        self.observation_space = spaces.Box(low, np.ones_like(low), dtype=np.float32)
        self._done = True
        self._leg_start: int | None = None      # distancia BFS al despacho al empezar el tramo de entrega
        self._leg_paid = False
        self._face_paid: set[str] = set()       # v8: estaciones objetivo cuyo face_bonus ya se pagó en este episodio
        # Cachés internes: sólo recompensa/diagnóstico/heurística; jamás se exponen a PPO.
        self._fields = {(b, s): self.layout.distance_field(s, b)
                        for b in (False, True) for s in self.layout.stations}
        self._obstacles = {b: self.layout.obstacles(b) for b in (False, True)}

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.action_space.seed(seed)
        blocked = bool((options or {}).get("blocked", self.blocked))
        x, y = self.layout.base
        self.state = WorldState(x, y, self.layout.data["initial_orientation"], 0.0,
                                self.config.battery_capacity, None, 0, "recoger", "P1",
                                0, self.config.max_steps, 0, 0, 0, blocked)
        self.picked_packages: set[str] = set()
        self.completed_packages: set[str] = set()
        self._leg_start, self._leg_paid = None, False
        self._face_paid = set()
        self._done = False
        self._reason = None
        return self._observation(), self._info()

    @property
    def position(self):
        return self.state.x, self.state.y

    def _free(self, cell):
        return (0 <= cell[0] < self.layout.width and 0 <= cell[1] < self.layout.height
                and cell not in self._obstacles[self.state.pasillo_bloqueado])

    def route_distance(self, station: str | None = None) -> int | None:
        target = station or self.state.objetivo
        if target is None:
            return 0
        return self._fields[self.state.pasillo_bloqueado, target].get(self.position)

    def manhattan_to(self, station: str | None) -> int:
        """Distancia Manhattan |dx|+|dy| (en celdas, sin obstáculos) de la posición actual a una estación."""
        if station is None:
            return 0
        tx, ty = self.layout.stations[station]
        return abs(self.state.x - tx) + abs(self.state.y - ty)

    def tray_level(self) -> int:
        """Posición discreta de la bandeja (0 = viaje); sin elevador siempre 0."""
        return 0

    def needed_tray_level(self) -> int:
        """Posición de bandeja que exige el objetivo actual (0 al entregar o sin objetivo)."""
        return 0

    def height_gap(self, station: str | None, needed: int) -> int:
        """Puestos de diferencia entre la bandeja y la exigida, solo si el robot está en una celda de interacción de `station`."""
        if station is None or self.route_distance(station) != 0:
            return 0
        return abs(self.tray_level() - needed)

    def carry_milestone_reached(self, target: str | None, distance_before: int | None, distance_after: int | None) -> bool:
        """Hito de entrega: la primera vez en un tramo que la distancia BFS al despacho baja a la mitad de la inicial.

        El tramo empieza en el primer paso con objetivo DELIVERY (la distancia de ese instante es la de referencia) y termina
        al cambiar de objetivo. Paga como mucho una vez por tramo, y cada tramo exige una recogida previa; alejarse y volver
        a acercarse no vuelve a pagar. Con la bandeja arriba el robot no se mueve, así que el hito exige haberla bajado.
        """
        if target != "DELIVERY":
            self._leg_start, self._leg_paid = None, False
            return False
        if self._leg_start is None:
            self._leg_start = distance_before
        if self._leg_paid or not self._leg_start or distance_after is None:
            return False
        if distance_after * 2 <= self._leg_start:
            self._leg_paid = True
            return True
        return False

    def face_bonus_reached(self, target: str | None) -> bool:
        """v8: primera vez en el episodio que el robot está en una celda de interacción de `target` mirando a la estación.

        Se paga como mucho una vez por estación y episodio (no por tramo), así que repetir recoger/soltar o salir y volver
        a la celda no vuelve a pagar; el máximo total es un pago por estación distinta visitada como objetivo.
        """
        if target is None or target in self._face_paid or self.target_station_distance(target) != 0:
            return False
        dx, dy = DIRECTIONS[self.state.theta]
        if (self.state.x + dx, self.state.y + dy) != self.layout.stations[target]:
            return False
        self._face_paid.add(target)
        return True

    def target_station_distance(self, station: str):
        return self.route_distance(station)

    def facing_target(self) -> bool:
        if self.state.objetivo is None:
            return False
        dx, dy = DIRECTIONS[self.state.theta]
        return (self.state.x + dx, self.state.y + dy) == self.layout.stations[self.state.objetivo]

    def _move(self, action: Action) -> bool:
        """Sólo movimiento/orientación/velocidad. Devuelve si hubo colisión."""
        state = self.state
        if action == Action.AVANZAR:
            dx, dy = DIRECTIONS[state.theta]
            destination = state.x + dx, state.y + dy
            if not self._free(destination):
                state.v = 0.0
                state.colisiones += 1
                return True
            state.x, state.y = destination
            state.v = 1.0
            state.distancia += self.layout.data["cell_meters"]
        elif action == Action.GIRAR_IZQUIERDA:
            state.theta = (state.theta - 1) % 4
        elif action == Action.GIRAR_DERECHA:
            state.theta = (state.theta + 1) % 4
        elif action == Action.FRENAR:
            state.v = 0.0
        return False

    def _interact(self, action=Action.CARGAR) -> tuple[bool, bool, bool]:
        """Recogida, entrega, invalidez: identidades y pedidos son monotónicos.

        CARGAR sólo recoge y DESCARGAR sólo entrega; SUBIR/BAJAR no existen sin elevador.
        """
        state = self.state
        if action in (Action.SUBIR, Action.BAJAR):
            state.interacciones_invalidas += 1
            return False, False, True
        if state.v != 0 or not self.facing_target():
            state.interacciones_invalidas += 1
            return False, False, True
        package = self.packages[state.pedido_actual]
        if (action == Action.CARGAR and state.etapa == "recoger" and state.carga is None
                and package not in self.picked_packages and package not in self.completed_packages):
            self.picked_packages.add(package)
            state.carga = package
            state.etapa = "entregar"
            state.objetivo = "DELIVERY"
            return True, False, False
        if (action == Action.DESCARGAR and state.etapa == "entregar" and state.carga == package
                and package in self.picked_packages and package not in self.completed_packages):
            self.completed_packages.add(package)
            state.carga = None
            state.entregas += 1
            state.pedido_actual += 1
            if state.entregas == self.orders:
                state.etapa, state.objetivo = "completada", None
            else:
                state.etapa, state.objetivo = "recoger", self.packages[state.pedido_actual]
            return False, True, False
        state.interacciones_invalidas += 1
        return False, False, True

    def step(self, action):
        if self._done:
            raise RuntimeError("El episodio terminó; llama reset() antes de step()")
        if not self.action_space.contains(action):
            raise ValueError(f"Acción fuera de Discrete(8): {action}")
        action = Action(int(action))
        state = self.state
        old_target = state.objetivo
        old_distance = self.route_distance(old_target)
        old_manhattan = self.manhattan_to(old_target)
        needed_level = self.needed_tray_level()
        costs = (self.config.forward_cost, self.config.turn_cost, self.config.turn_cost,
                 self.config.brake_cost, self.config.interact_cost, self.config.interact_cost,
                 self.config.brake_cost, self.config.brake_cost)
        used = min(state.bateria, costs[action])
        state.bateria = max(0.0, state.bateria - used)
        state.tiempo += 1
        state.tiempo_restante = max(0, self.config.max_steps - state.tiempo)
        collision = self._move(action)
        face = self.face_bonus_reached(old_target)
        pickup = delivery = invalid = False
        if action in (Action.CARGAR, Action.DESCARGAR, Action.SUBIR, Action.BAJAR):
            pickup, delivery, invalid = self._interact(action)
        # Mantener el objetivo previo evita recompensa por el salto de etapa.
        new_distance = self.route_distance(old_target)
        delta = float(old_distance - new_distance) if old_distance is not None and new_distance is not None else 0.0
        success = state.entregas == self.orders
        target_distance = self.manhattan_to(old_target)
        manhattan_delta = float(old_manhattan - target_distance)   # mismo objetivo antes y después: sin salto al cambiar de etapa
        height_gap = float(self.height_gap(old_target, needed_level))
        milestone = self.carry_milestone_reached(old_target, old_distance, new_distance)
        components = reward_components(self.reward_config, distance_delta=delta,
                                       battery_used=used, pickup=pickup, delivery=delivery,
                                       completion=success, collision=collision, invalid=invalid,
                                       target_distance=target_distance, manhattan_delta=manhattan_delta,
                                       height_gap=height_gap, milestone=milestone, face=face)
        reward = float(sum(components.values()))
        state.recompensa_total += reward
        unreachable = not success and self.route_distance() is None
        terminated = bool(success or state.bateria <= 1e-9 or unreachable)
        truncated = bool(state.tiempo >= self.config.max_steps and not terminated)
        self._reason = ("success" if success else "battery_depleted" if state.bateria <= 1e-9
                        else "unreachable_target" if unreachable else "time_limit" if truncated else None)
        self._done = terminated or truncated
        return self._observation(), reward, terminated, truncated, self._info(components)

    def sensor_distances(self) -> np.ndarray:
        """8 rayos en ejes del mundo; metros hasta el centro del primer obstáculo."""
        values = []
        for dx, dy in RAYS:
            distance = float(self.config.sensor_range)
            for step in range(1, self.config.sensor_range + 1):
                meters = step * math.hypot(dx, dy)
                if meters > self.config.sensor_range:
                    break
                if not self._free((self.state.x + step * dx, self.state.y + step * dy)):
                    distance = meters
                    break
            values.append(distance)
        return np.asarray(values, dtype=np.float32)

    def interactable_stations(self):
        return tuple(self.layout.stations)

    def can_interact_from_here(self, station) -> bool:
        return True

    def facing_interactable(self) -> bool:
        """El tramo de celda frente al robot es una estación con la que se puede interactuar."""
        dx, dy = DIRECTIONS[self.state.theta]
        ahead = (self.state.x + dx, self.state.y + dy)
        return any(self.layout.stations[name] == ahead and self.can_interact_from_here(name)
                   for name in self.interactable_stations())

    def elevation(self) -> float:
        """Elevación normalizada de la bandeja; sin elevador siempre 0."""
        return 0.0

    def target_elevation(self) -> float:
        return 0.0

    def _observation(self) -> np.ndarray:
        state = self.state
        target = self.layout.stations[state.objetivo] if state.objetivo else self.position
        wm, hm = self.layout.width - 1, self.layout.height - 1
        obs = np.zeros(self.OBSERVATION_SIZE, dtype=np.float32)
        obs[:8] = self.sensor_distances() / self.config.sensor_range
        obs[8:10] = (state.x / wm, state.y / hm)
        obs[10:12] = (target[0] / wm, target[1] / hm)
        obs[12 + state.theta] = 1.0
        obs[16] = state.v
        obs[17] = state.bateria / self.config.battery_capacity
        obs[18] = self.carried_fraction()
        obs[19:22] = [float(state.etapa == stage) for stage in ("recoger", "entregar", "completada")]
        obs[22] = state.tiempo_restante / self.config.max_steps
        obs[23] = state.entregas / self.orders
        obs[24] = float(self.facing_interactable())
        obs[25] = self.elevation()
        obs[26] = self.target_elevation()
        if not np.isfinite(obs).all() or not self.observation_space.contains(obs):
            raise RuntimeError(f"Observación inválida: {obs}")
        return obs

    def carried_fraction(self) -> float:
        return float(self.state.carga is not None)

    def snapshot(self) -> dict:
        return {**asdict(self.state), "paquetes_recogidos": sorted(self.picked_packages),
                "paquetes_completados": sorted(self.completed_packages)}

    def _info(self, components=None) -> dict:
        state = self.state
        return {"success": state.entregas == self.orders,
                "failure": self._reason in ("battery_depleted", "unreachable_target"),
                "end_reason": self._reason, "steps": state.tiempo,
                "simulated_time": state.tiempo * self.config.step_seconds,
                "distance": state.distancia,
                "battery_used": self.config.battery_capacity - state.bateria,
                "deliveries": state.entregas, "collisions": state.colisiones,
                "invalid_interactions": state.interacciones_invalidas,
                "total_reward": state.recompensa_total, "state": self.snapshot(),
                "reward_components": components or {key: 0.0 for key in asdict(self.reward_config)},
                "layout_sha256": self.layout.digest}

    def render(self):
        state = self.state
        text = self.layout.ascii(self.position, state.theta, state.pasillo_bloqueado)
        text += (f"\nt={state.tiempo}s batería={state.bateria:.1f} carga={state.carga} "
                 f"objetivo={state.objetivo} entregas={state.entregas}/{self.orders}")
        if self.render_mode == "human":
            print(text)
            return None
        return text

    def close(self):
        pass
