"""Misiones optativas; conserva física, recompensas y contrato observado v0.1."""
from copy import deepcopy
import math
from envs.env import Action, WarehouseRushEnv
from envs.handling import LiftConfig
from envs.inventory import Inventory
from envs.layout import Layout, PACKING_LAYOUT


class MakeupMissionEnv(WarehouseRushEnv):
    def __init__(self, orders=1, blocked=False, layout_path=None, simulation=None,
                 rewards=None, render_mode=None, *, capacity=3, inventory=None, restock=False,
                 lines=None, max_per_line=None):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Capacidad inválida')
        super().__init__(orders, blocked, layout_path or PACKING_LAYOUT,
                         simulation=simulation, rewards=rewards, render_mode=render_mode)
        self.capacity = capacity
        self.order_lines = lines                       # nº fijo de SKUs por pedido (None = 1-3 al azar)
        self.max_per_line = max_per_line or capacity
        self.lift_config = LiftConfig()
        self.restock = bool(restock) and inventory is None   # entrenamiento: stock nuevo en cada episodio
        self.inventory = inventory or Inventory()
        data = deepcopy(self.layout.data)
        for i, rack in enumerate(data['racks'], 1):
            # Cara norte: celda física del estante; interacción sólo desde adyacencia.
            data['stations'][f'E{i:02d}'] = rack['bounds'][:2]
        self.layout = Layout(data, self.layout.source)
        self._fields = {(b, s): self.layout.distance_field(s, b) for b in (False, True) for s in self.layout.stations}
        self._obstacles = {b: self.layout.obstacles(b) for b in (False, True)}
        for field in self._fields.values():
            if self.layout.base not in field:
                raise ValueError('Punto de picking inaccesible')
        self.order_id = None

    def reset(self, *, seed=None, options=None):
        if self.restock:
            self.inventory = Inventory()
        elif self.order_id:
            self.inventory.close(self.order_id, time=self.state.tiempo)
        # Con seed explícita el pedido es reproducible; sin ella se sortea desde el RNG del entorno.
        order_seed = seed if seed is not None else int(self.np_random.integers(2 ** 31 - 1))
        order = self.inventory.generate(order_seed, max_per_line=self.max_per_line, lines=self.order_lines)
        self.order_id = order['id']
        self.lines = order['lines']
        self.orders = len(self.lines)
        self.packages = tuple(l['sku'] for l in self.lines)
        self.lift_height = self.lift_config.travel_height
        self.lift_target = self.lift_height
        self.lift_phase = 'idle'
        self.lift_sku = None
        self.lift_energy = 0.0
        self.dispatch_visits = 0
        self.blocked_lift_moves = 0
        self.plan = {}
        self.budget_failure = False
        super().reset(seed=seed, options=options)
        self._assign_next_target()
        return self._observation(), self._info()

    @property
    def carried_lines(self):
        return [line for line in self.inventory.orders[self.order_id]['lines']
                if line['picked'] > line['delivered']]

    def _candidate_budget(self, index, line):
        blocked = self.state.pasillo_bloqueado
        outward = self._fields[blocked, line['rack']].get(self.position, math.inf)
        back_field = self._fields[blocked, 'DELIVERY']
        back = min((back_field.get(p, math.inf) for p in self.layout.approaches(line['rack'], blocked)), default=math.inf)
        lift_steps = self.lift_config.cycles(line['height_m'])
        current_lowering = self.lift_config.index(self.lift_height)
        # Margen explícito para orientación, frenado y transferencia. No es una
        # optimización global: la estimación se recalcula después de cada recogida.
        steps = outward + back + lift_steps + current_lowering + 12
        lift_energy = 2 * abs(line['height_m'] - self.lift_config.travel_height) * self.lift_config.energy_per_meter
        energy = steps * max(self.config.forward_cost, self.config.turn_cost,
                             self.config.brake_cost, self.config.interact_cost) + lift_energy + self.lift_config.battery_reserve
        feasible = energy <= self.state.bateria and steps <= self.state.tiempo_restante
        return dict(index=index, line=line, score=outward + lift_steps, steps=steps,
                    energy=energy, feasible=feasible)

    def _assign_next_target(self):
        state = self.state
        carried = sum(l['picked'] - l['delivered'] for l in self.carried_lines)
        state.carga = self.carried_lines[0]['sku'] if carried else None
        pending = [(i, l) for i, l in enumerate(self.inventory.orders[self.order_id]['lines']) if not l['picked']]
        fits = [(i, l) for i, l in pending if l['quantity'] <= self.capacity - carried]
        candidates = sorted((self._candidate_budget(i, l) for i, l in fits), key=lambda c: (c['score'], c['line']['sku']))
        feasible = [c for c in candidates if c['feasible']]
        if feasible or (not carried and candidates):
            selected = (feasible or candidates)[0]
            state.pedido_actual, line = selected['index'], selected['line']
            state.etapa, state.objetivo = 'recoger', line['rack']
            self.budget_failure = not selected['feasible']
            self.inventory.orders[self.order_id]['state'] = 'PICKING'
            self.plan = dict(reason='insufficient_budget' if self.budget_failure else 'nearby_product',
                             next_sku=line['sku'], estimated_steps=selected['steps'],
                             estimated_energy=round(selected['energy'], 2))
        elif carried:
            state.etapa, state.objetivo = 'entregar', 'DELIVERY'
            self.inventory.orders[self.order_id]['state'] = 'IN_TRANSIT'
            self.plan = dict(reason='capacity' if pending and not fits else 'battery_or_time' if pending else 'all_picked')
        else:
            state.etapa, state.objetivo = 'completada', None
            self.plan = dict(reason='complete')

    def mechanism_snapshot(self):
        return dict(height=self.lift_height, target=self.lift_target, phase=self.lift_phase,
                    sku=self.lift_sku, energy=self.lift_energy, dispatch_visits=self.dispatch_visits,
                    blocked_moves=self.blocked_lift_moves, plan=deepcopy(self.plan), budget_failure=self.budget_failure)

    def restore_mechanism(self, record):
        if not record:
            return
        index = self.lift_config.index(record['height'])
        self.lift_height = self.lift_target = self.lift_config.positions[index]
        self.lift_phase = 'idle' if index == 0 else 'ready'
        self.lift_sku, self.lift_energy = record['sku'], record['energy']
        self.dispatch_visits, self.blocked_lift_moves = record['dispatch_visits'], record['blocked_moves']
        self.plan, self.budget_failure = record['plan'], record['budget_failure']

    def _lift_event(self, kind):
        self.inventory.event(self.inventory.orders[self.order_id], kind, self.state.tiempo)

    def interactable_stations(self):
        return (*(f'E{i:02d}' for i in range(1, len(self.layout.data['racks']) + 1)), 'DELIVERY')

    def can_interact_from_here(self, station):
        if station == 'DELIVERY':
            return self.position in self.layout.approaches('DELIVERY', self.state.pasillo_bloqueado)
        return True

    def tray_level(self):
        return self.lift_config.index(self.lift_height)

    def needed_tray_level(self):
        s = self.state
        if s.etapa != 'recoger' or s.objetivo is None or not self.lines:
            return 0
        return self.lift_config.index(self.lines[s.pedido_actual]['height_m'])

    # --- v9: potencial por etapas (Phi en [0,1], solo función del estado) ---
    POTENTIAL_WEIGHTS = dict(stow=0.10, navigate=0.40, face=0.20, tray=0.30)   # suman 1: reparto dentro de un tramo

    def _max_route(self, station):
        key = (self.state.pasillo_bloqueado, station)
        cache = self.__dict__.setdefault('_max_route_cache', {})
        if key not in cache:
            cache[key] = max(self._fields[key].values()) or 1
        return cache[key]

    def potential(self):
        """Phi(s) = (K + phi_tramo) / (2n): K = líneas recogidas + entregadas; phi_tramo en [0,1] mide el avance del tramo actual.

        phi_tramo = 0.10 bandeja guardada mientras se viaja + 0.40 (1 - d/d_max) por distancia BFS a la celda de interacción
        + 0.20 ya en la celda y mirando a la estación + 0.30 bandeja en la altura exigida (1 - |nivel - exigido|/3).
        En la celda de interacción la bandeja guardada cuenta como cumplida para que subirla no reste. Sin objetivo, phi_tramo = 0.
        """
        s, w = self.state, self.POTENTIAL_WEIGHTS
        units = len(self.picked_packages) + s.entregas
        total = 2 * self.orders
        if s.objetivo is None or not self.lines:
            return min(1.0, units / total)
        d = self.route_distance(s.objetivo)
        level = self.tray_level()
        nav = 0.0 if d is None else 1.0 - d / self._max_route(s.objetivo)
        at_cell = d == 0
        phi = w['navigate'] * max(0.0, nav) + (w['stow'] if (level == 0 or at_cell) else 0.0)
        if at_cell and self.facing_target():
            phi += w['face'] + w['tray'] * (1.0 - abs(level - self.needed_tray_level()) / 3.0)
        return min(1.0, (units + min(1.0, phi)) / total)

    def elevation(self):
        return self.lift_config.normalized(self.lift_height)

    def target_elevation(self):
        s = self.state
        if s.etapa != 'recoger' or not self.lines:
            return 0.0
        return self.lift_config.normalized(self.lines[s.pedido_actual]['height_m'])

    def carried_fraction(self):
        return min(1.0, sum(l['picked'] - l['delivered'] for l in self.carried_lines) / self.capacity)

    def _move(self, action):
        if self.budget_failure:
            self.state.v = 0.
            return False
        if self.lift_phase != 'idle':
            # Con la bandeja arriba el robot no avanza ni gira; sólo SUBIR/BAJAR/CARGAR/FRENAR.
            self.state.v = 0.
            if action in (Action.AVANZAR, Action.GIRAR_IZQUIERDA, Action.GIRAR_DERECHA):
                self.blocked_lift_moves += 1
            return False
        return super()._move(action)

    def facing_target(self):
        if self.state.objetivo == 'DELIVERY' and self.position not in self.layout.approaches('DELIVERY', self.state.pasillo_bloqueado):
            return False
        return super().facing_target()

    def _lift_step(self, action):
        """SUBIR/BAJAR: una posición de la bandeja por acción (0.55 m, 0.99, 1.79, 2.60 m)."""
        s, cfg = self.state, self.lift_config
        index, top = cfg.index(self.lift_height), len(cfg.positions) - 1
        if action == Action.SUBIR:
            if index >= top:
                s.interacciones_invalidas += 1
                return False, False, True
            if index == 0:
                if s.v != 0 or s.etapa != 'recoger' or not self.facing_target():
                    s.interacciones_invalidas += 1
                    return False, False, True
                line = self.lines[s.pedido_actual]
                self.lift_sku = line['sku']
                self._lift_event(f'LIFT_START:{line["level"]}')
            new = index + 1
        else:
            if index == 0:
                s.interacciones_invalidas += 1
                return False, False, True
            new = index - 1
            self._lift_event('LIFT_LOWERING')
        height = cfg.positions[new]
        distance = min(abs(height - self.lift_height), s.bateria / cfg.energy_per_meter)
        used = distance * cfg.energy_per_meter
        s.bateria = max(0., s.bateria - used)
        self._lift_used += used
        self.lift_energy += used
        self.lift_height = self.lift_target = height
        self.lift_phase = 'idle' if new == 0 else 'ready'
        if new == 0:
            self.lift_sku = None
            self._lift_event('LIFT_STOWED')
        elif s.etapa == 'recoger' and abs(height - self.lines[s.pedido_actual]['height_m']) < 1e-9:
            self._lift_event('LIFT_READY')
        return False, False, False

    def _interact(self, action):
        s = self.state
        if self.budget_failure:
            return False, False, False
        if action in (Action.SUBIR, Action.BAJAR):
            return self._lift_step(action)
        if s.v != 0 or not self.facing_target():
            s.interacciones_invalidas += 1
            return False, False, True
        if action == Action.CARGAR and s.etapa == 'recoger':
            line = self.lines[s.pedido_actual]
            used = sum(l['picked'] - l['delivered'] for l in self.carried_lines)
            if (self.lift_phase == 'ready' and abs(self.lift_height - line['height_m']) < 1e-9
                    and used + line['quantity'] <= self.capacity
                    and self.inventory.pick(self.order_id, line['sku'], line['quantity'], s.tiempo)):
                self.picked_packages.add(line['sku'])
                self._assign_next_target()
                return True, False, False
        elif action == Action.DESCARGAR and s.etapa == 'entregar' and self.carried_lines and self.lift_phase == 'idle':
            self.dispatch_visits += 1
            for line in self.carried_lines:
                if self.inventory.deliver(self.order_id, line['sku'], s.tiempo):
                    self.completed_packages.add(line['sku'])
                    s.entregas += 1
            self._assign_next_target()
            return False, True, False
        s.interacciones_invalidas += 1
        return False, False, True

    def step(self, action):
        self._lift_used = 0.
        obs, reward, terminated, truncated, info = super().step(action)
        if self._lift_used:
            penalty = self.reward_config.battery * self._lift_used
            reward += penalty
            self.state.recompensa_total += penalty
            info['reward_components']['battery'] += penalty
        if self.budget_failure and not info['success']:
            self._done, self._reason = True, 'insufficient_budget'
            terminated, truncated = True, False
        if (terminated or truncated) and not info['success']:
            self.inventory.close(self.order_id, failed=True, time=self.state.tiempo)
        info = self._info(info['reward_components'])
        return obs, reward, terminated, truncated, info

    def _info(self, components=None):
        info = super()._info(components)
        info['failure'] = info['failure'] or self._reason == 'insufficient_budget'
        return info

    def snapshot(self):
        return dict(**super().snapshot(), inventory=self.inventory.snapshot(),
                    order=deepcopy(self.inventory.orders[self.order_id]), capacity=self.capacity,
                    lift=self.mechanism_snapshot(),
                    cargo_lines=[dict(sku=l['sku'], quantity=l['picked'] - l['delivered'],
                                      level=l['level'], subcategory=l['subcategory']) for l in self.carried_lines])
