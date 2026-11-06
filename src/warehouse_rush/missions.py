"""Misiones optativas; conserva física, recompensas y contrato observado v0.1."""
from copy import deepcopy
from warehouse_rush.env import WarehouseRushEnv
from warehouse_rush.inventory import Inventory
from warehouse_rush.layout import Layout


class MakeupMissionEnv(WarehouseRushEnv):
    def __init__(self, *args, capacity=3, inventory=None, **kwargs):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('Capacidad inválida')
        super().__init__(*args, **kwargs)
        self.capacity = capacity
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
        if self.order_id:
            self.inventory.close(self.order_id, time=self.state.tiempo)
        order = self.inventory.generate(seed, max_per_line=self.capacity)
        self.order_id = order['id']
        self.lines = order['lines']
        self.orders = len(self.lines)
        self.packages = tuple(l['sku'] for l in self.lines)
        super().reset(seed=seed, options=options)
        self.state.objetivo = self.lines[0]['rack']
        return self._observation(), self._info()

    @property
    def carried_lines(self):
        return [line for line in self.inventory.orders[self.order_id]['lines']
                if line['picked'] > line['delivered']]

    def _assign_next_target(self):
        state = self.state
        carried = sum(l['picked'] - l['delivered'] for l in self.carried_lines)
        state.carga = self.carried_lines[0]['sku'] if carried else None
        remaining = [(i, l) for i, l in enumerate(self.inventory.orders[self.order_id]['lines'])
                     if not l['picked'] and l['quantity'] <= self.capacity - carried]
        if remaining:
            state.pedido_actual, line = remaining[0]
            state.etapa, state.objetivo = 'recoger', line['rack']
            self.inventory.orders[self.order_id]['state'] = 'PICKING'
        elif carried:
            state.etapa, state.objetivo = 'entregar', 'DELIVERY'
            self.inventory.orders[self.order_id]['state'] = 'IN_TRANSIT'
        else:
            state.etapa, state.objetivo = 'completada', None

    def _interact(self):
        s = self.state
        if s.v != 0 or not self.facing_target():
            s.interacciones_invalidas += 1
            return False, False, True
        if s.etapa == 'recoger':
            line = self.lines[s.pedido_actual]
            used = sum(l['picked'] - l['delivered'] for l in self.carried_lines)
            if used + line['quantity'] <= self.capacity and self.inventory.pick(
                    self.order_id, line['sku'], line['quantity'], s.tiempo):
                self.picked_packages.add(line['sku'])
                self._assign_next_target()
                return True, False, False
        elif s.etapa == 'entregar' and self.carried_lines:
            for line in self.carried_lines:
                if self.inventory.deliver(self.order_id, line['sku'], s.tiempo):
                    self.completed_packages.add(line['sku'])
                    s.entregas += 1
            self._assign_next_target()
            return False, True, False
        s.interacciones_invalidas += 1
        return False, False, True

    def step(self, action):
        obs, reward, terminated, truncated, info = super().step(action)
        if (terminated or truncated) and not info['success']:
            self.inventory.close(self.order_id, failed=True, time=self.state.tiempo)
            info = self._info(info['reward_components'])
        return obs, reward, terminated, truncated, info

    def snapshot(self):
        return dict(**super().snapshot(), inventory=self.inventory.snapshot(),
                    order=deepcopy(self.inventory.orders[self.order_id]), capacity=self.capacity,
                    cargo_lines=[dict(sku=l['sku'], quantity=l['picked'] - l['delivered'],
                                      level=l['level'], subcategory=l['subcategory']) for l in self.carried_lines])
