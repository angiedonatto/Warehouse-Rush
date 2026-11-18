"""Geometría, sensores y búsquedas de referencia sobre el mismo JSON."""

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

Cell = tuple[int, int]
DIRECTIONS: tuple[Cell, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))
RAYS: tuple[Cell, ...] = ((0, -1), (1, -1), (1, 0), (1, 1),
                          (0, 1), (-1, 1), (-1, 0), (-1, -1))
DEFAULT_LAYOUT = Path(__file__).resolve().parents[2] / "configs/layout_v0.1.json"
if not DEFAULT_LAYOUT.is_file():  # Instalaciones wheel: un enlace al JSON canónico se empaqueta.
    DEFAULT_LAYOUT = Path(__file__).parent / "configs/layout_v0.1.json"

WIDE_LAYOUT = DEFAULT_LAYOUT.with_name("layout_v0.3.json")
PACKING_LAYOUT = DEFAULT_LAYOUT.with_name("layout_v0.4.json")


@dataclass(frozen=True)
class Layout:
    data: dict
    source: Path

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Layout":
        source = Path(path) if path else DEFAULT_LAYOUT
        layout = cls(json.loads(source.read_text()), source.resolve())
        layout.check_geometry()
        return layout

    @property
    def width(self) -> int:
        return self.data["width"]

    @property
    def height(self) -> int:
        return self.data["height"]

    @property
    def base(self) -> Cell:
        return tuple(self.data["base"])

    @property
    def stations(self) -> dict[str, Cell]:
        return {name: tuple(cell) for name, cell in self.data["stations"].items()}

    @property
    def digest(self) -> str:
        return sha256(json.dumps(self.data, sort_keys=True).encode()).hexdigest()

    @property
    def racks(self) -> set[Cell]:
        cells = set()
        for rack in self.data["racks"]:
            x0, y0, x1, y1 = rack["bounds"]
            cells.update((x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1))
        return cells

    @property
    def walls(self) -> set[Cell]:
        return ({(x, y) for x in range(self.width) for y in (0, self.height - 1)}
                | {(x, y) for y in range(self.height) for x in (0, self.width - 1)}
                | {tuple(c) for c in self.data["internal_walls"]})

    @property
    def dispatch_cells(self) -> set[Cell]:
        area = self.data.get('dispatch_area')
        if not area:
            return set()
        x0, y0, x1, y1 = area['bounds']
        return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}

    def obstacles(self, blocked: bool = False) -> set[Cell]:
        # Las estaciones tienen huella física; se interactúa desde la celda adyacente.
        return (self.walls | self.racks | self.dispatch_cells | set(self.stations.values())
                | ({tuple(c) for c in self.data["blockable_cells"]} if blocked else set()))

    def free(self, cell: Cell, blocked: bool = False) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height and cell not in self.obstacles(blocked)

    def neighbors(self, cell: Cell, blocked: bool = False):
        for dx, dy in DIRECTIONS:
            candidate = cell[0] + dx, cell[1] + dy
            if self.free(candidate, blocked):
                yield candidate

    def approaches(self, station: str, blocked: bool = False) -> set[Cell]:
        if station == 'DELIVERY' and self.data.get('dispatch_area'):
            cell = tuple(self.data['dispatch_area']['approach'])
            return {cell} if self.free(cell, blocked) else set()
        return set(self.neighbors(self.stations[station], blocked))

    def distance_field(self, station: str, blocked: bool = False) -> dict[Cell, int]:
        distances = {cell: 0 for cell in self.approaches(station, blocked)}
        queue = deque(distances)
        while queue:
            current = queue.popleft()
            for neighbor in self.neighbors(current, blocked):
                if neighbor not in distances:
                    distances[neighbor] = distances[current] + 1
                    queue.append(neighbor)
        return distances

    def check_geometry(self) -> None:
        if self.width < 5 or self.height < 5 or len(self.data["racks"]) != 6:
            raise ValueError("El mapa debe tener dimensiones válidas y seis racks")
        if set(self.stations) != {"P1", "P2", "DELIVERY"}:
            raise ValueError("Se requieren las estaciones P1, P2 y DELIVERY")
        locations = [self.base, *self.stations.values()]
        if len(set(locations)) != len(locations):
            raise ValueError("Base y estaciones deben ser diferentes")
        for x, y in locations:
            if not (0 < x < self.width - 1 and 0 < y < self.height - 1):
                raise ValueError("Base/estaciones fuera del interior del mapa")
            if (x, y) in self.walls | self.racks:
                raise ValueError("Base/estaciones solapadas con obstáculos")
        if self.data.get('dispatch_area'):
            area = self.data['dispatch_area']
            x0, y0, x1, y1 = area['bounds']
            if not (0 < x0 <= x1 < self.width - 1 and 0 < y0 <= y1 < self.height - 1):
                raise ValueError('Estación de empaque fuera del mapa')
            if self.dispatch_cells & (self.walls | self.racks | {self.base, self.stations['P1'], self.stations['P2']}):
                raise ValueError('Estación de empaque solapada con obstáculos o estaciones')
            if self.stations['DELIVERY'] not in self.dispatch_cells:
                raise ValueError('El despacho debe estar dentro de la estación de empaque')
            approach = tuple(area['approach'])
            target = self.stations['DELIVERY']
            if not self.free(approach) or abs(approach[0] - target[0]) + abs(approach[1] - target[1]) != 1:
                raise ValueError('Punto de descarga inválido')
        for cell in map(tuple, self.data["blockable_cells"]):
            if not self.free(cell) or cell in locations:
                raise ValueError("El bloqueo debe ocupar un tramo inicialmente libre")

    def validate_routes(self) -> dict:
        result = {}
        for blocked in (False, True):
            label = "blocked" if blocked else "normal"
            distances = {}
            for station in self.stations:
                field = self.distance_field(station, blocked)
                if self.base not in field:
                    raise ValueError(f"{station} no accesible: {label}")
                # Todos los puntos de interacción pertenecen al componente de BASE.
                for other in self.stations:
                    if not self.approaches(other, blocked) <= field.keys():
                        raise ValueError(f"Estaciones desconectadas: {label}")
                distances[station] = field[self.base]
            result[label] = distances
        if not any(result["blocked"][s] > result["normal"][s] for s in self.stations):
            raise ValueError("El bloqueo no altera ninguna ruta desde BASE")
        return result

    def ascii(self, position: Cell | None = None, theta: int = 0, blocked: bool = False) -> str:
        grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
        for x, y in self.walls:
            grid[y][x] = "#"
        for x, y in self.racks:
            grid[y][x] = "R"
        for x, y in self.dispatch_cells:
            grid[y][x] = 'C'
        for name, (x, y) in self.stations.items():
            grid[y][x] = {"P1": "1", "P2": "2", "DELIVERY": "D"}.get(name, "E")
        x, y = self.base
        grid[y][x] = "B"
        for x, y in map(tuple, self.data["blockable_cells"]):
            grid[y][x] = "X" if blocked else ":"
        if position is not None:
            x, y = position
            grid[y][x] = "^>v<"[theta]
        return "\n".join("".join(row) for row in grid)
