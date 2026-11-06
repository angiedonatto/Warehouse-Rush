"""Catálogo provisional y libro de inventario local, independiente de Three.js."""
from copy import deepcopy
from random import Random
from threading import RLock
from uuid import uuid4

CATEGORIES = [
    ('Maquillaje', ['Ojos', 'Rostro', 'Labios']),
    ('Cuidado de la piel', ['Corporal', 'Cuidado facial', 'Facial hombres']),
    ('Brochas y esponjas', ['Brochas individuales', 'Esponjas', 'Kits de brochas']),
    ('Accesorios', ['Bolsos y cosmetiqueras', 'Espejos', 'Pestañas']),
    ('Capilar', ['Accesorios para cabello', 'Peines', 'Mascarillas capilares']),
    ('Disney', ['Princesas', 'Villanos', 'Toy Story']),
]
CATALOG = {f'TMP-E{i:02d}-L{j}': dict(sku=f'TMP-E{i:02d}-L{j}', rack=f'E{i:02d}',
           level=f'E{i:02d}-L{j}', category=category, subcategory=sub, temporary=True)
           for i, (category, subs) in enumerate(CATEGORIES, 1) for j, sub in enumerate(subs, 1)}


class Inventory:
    def __init__(self, stock=None):
        self.lock = RLock()
        self.initial = dict(stock if stock is not None else {sku: 5 for sku in CATALOG})
        if any(sku not in CATALOG or type(q) is not int or q < 0 for sku, q in self.initial.items()):
            raise ValueError('Inventario inicial inválido')
        self.total = self.initial.copy()
        self.orders = {}

    def reserved(self, sku):
        return sum(line['reserved'] for order in self.orders.values() for line in order['lines'] if line['sku'] == sku)

    def available(self, sku):
        return self.total.get(sku, 0) - self.reserved(sku)

    def event(self, order, kind, time):
        order['events'].append(dict(kind=kind, time=time))

    def reserve(self, lines, order_id=None, time=0):
        with self.lock:
            identity = order_id or str(uuid4())
            requested = sorted(lines.items())
            if identity in self.orders:
                order = self.orders[identity]
                if sorted((l['sku'], l['quantity']) for l in order['lines']) != requested:
                    raise ValueError('ID reutilizado con otras líneas')
                return deepcopy(order)
            if not requested or any(s not in CATALOG or type(q) is not int or q <= 0 for s, q in requested):
                raise ValueError('Líneas inválidas')
            order = dict(id=identity, state='GENERATED', lines=[dict(**CATALOG[s], quantity=q,
                         reserved=0, picked=0, delivered=0, pending_return=0) for s, q in requested], events=[])
            self.orders[identity] = order
            self.event(order, 'GENERATED', time)
            valid = all(q <= self.available(s) for s, q in requested)
            order['state'] = 'RESERVED' if valid else 'REJECTED'
            if valid:
                for line in order['lines']:
                    line['reserved'] = line['quantity']
            self.event(order, order['state'], time)
            self.check()
            return deepcopy(order)

    def generate(self, seed=None, max_per_line=3, time=0):
        if type(max_per_line) is not int or max_per_line < 1:
            raise ValueError('Límite de línea inválido')
        with self.lock:
            rng = Random(seed)
            skus = sorted(s for s in self.total if self.available(s) > 0)
            if not skus:
                raise ValueError('No puede generarse una orden válida: sin stock disponible')
            selected = rng.sample(skus, rng.randint(1, min(3, len(skus))))
            return self.reserve({s: rng.randint(1, min(max_per_line, self.available(s))) for s in selected}, time=time)

    def pick(self, identity, sku, quantity, time=0):
        with self.lock:
            order = self.orders[identity]
            line = next(l for l in order['lines'] if l['sku'] == sku)
            if quantity != line['quantity']:
                raise ValueError('Recogida debe ser exacta')
            if order['state'] in ('FAILED', 'CANCELLED', 'REJECTED'):
                raise ValueError('Orden cerrada')
            if line['picked']:
                return False
            if line['reserved'] != quantity:
                raise ValueError('Sin reserva')
            self.total[sku] -= quantity
            line.update(reserved=0, picked=quantity)
            order['state'] = 'IN_TRANSIT'
            self.event(order, f'PICK:{sku}:{quantity}', time)
            self.check()
            return True

    def deliver(self, identity, sku, time=0):
        with self.lock:
            order = self.orders[identity]
            line = next(l for l in order['lines'] if l['sku'] == sku)
            if order['state'] in ('FAILED', 'CANCELLED', 'REJECTED') or not line['picked']:
                raise ValueError('Carga no entregable')
            if line['delivered']:
                return False
            line['delivered'] = line['picked']
            order['state'] = 'DELIVERED' if all(l['delivered'] == l['quantity'] for l in order['lines']) else 'PICKING'
            self.event(order, f'DELIVER:{sku}', time)
            self.check()
            return True

    def close(self, identity, failed=False, time=0):
        with self.lock:
            order = self.orders[identity]
            if order['state'] in ('DELIVERED', 'FAILED', 'CANCELLED', 'REJECTED'):
                return False
            order['state'] = 'FAILED' if failed else 'CANCELLED'
            for line in order['lines']:
                line['reserved'] = 0
                line['pending_return'] = line['picked'] - line['delivered']
            self.event(order, order['state'], time)
            self.check()
            return True

    def check(self):
        for sku, initial in self.initial.items():
            lines = [l for o in self.orders.values() for l in o['lines'] if l['sku'] == sku and o['state'] != 'REJECTED']
            assert 0 <= self.reserved(sku) <= self.total[sku]
            assert initial == self.total[sku] + sum(l['picked'] for l in lines)
            for l in lines:
                assert 0 <= l['delivered'] <= l['picked'] <= l['quantity']
                assert l['reserved'] in (0, l['quantity'])
                assert 0 <= l['pending_return'] <= l['picked'] - l['delivered']

    def snapshot(self):
        with self.lock:
            return dict(products=[dict(**CATALOG[s], stock_total=q, stock_reserved=self.reserved(s),
                        stock_available=self.available(s)) for s, q in self.total.items()], orders=deepcopy(list(self.orders.values())))
