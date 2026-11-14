# Environment versions (warehouse-v1 to warehouse-v5)

Everything below is true at 2026-11-13 on branch `dev/lis` (last code commit `2b80031`, last experiment commit `64e3c77`). The authoritative documents live in the repo; read them before changing anything:
`envs/CONTRATO.md` (frozen contract), `docs/ambiente-v0.1.md` ... `docs/ambiente-v0.5.md` (one sheet per version), `docs/decisiones.md` (dated decision log, Spanish).

**Rule:** any change to observation order/units/ranges, actions, dt, physics **or the reward function** bumps `ENV_VERSION` and gets an annotated git tag `env/warehouse-vN` on the commit that introduces it. Old tags must keep pointing at the code that produced the old results. Adding a reward term that defaults to 0 is still a reward change: it was bumped (v4, v5).

## Timeline

| Version | Tag -> commit | What changed | Sheet |
|---|---|---|---|
| `warehouse-v1` (0.1.0) | (history; `experiment-001` tag is the first deploy) | Two floor pickup stations P1/P2, one delivery cell, `Box(22)` observation (relative direction to target), `Discrete(5)` (AVANZAR, GIRAR_I, GIRAR_D, FRENAR, INTERACTUAR), map 17x13, battery 100, 250 steps. N1/N2/N3 = 1 order / 2 orders / 2 orders with the closed aisle | `docs/ambiente-v0.1.md` |
| `warehouse-v2` (0.2.0) | `env/warehouse-v2` -> `b878762` | **Makeup mode only** (dev/angie merged). `Box(27)`, `Discrete(8)`. Inventory + orders (18 SKUs `TMP-E##-L#`, 5 units each, 6 racks x 3 levels), telescopic tray with 4 positions, conveyor/box at dispatch, map 25x19 (`layout_v0.4.json`), battery 180, 400 steps, capacity 3. Level `m1` | `docs/ambiente-v0.2.md` |
| `warehouse-v3` (0.3.0) | `env/warehouse-v3` -> `30c34fb` | Reward coefficients become a **per-run parameter**: `recompensa:` block in the experiment YAML -> `config_sha256`, `metadata.json` (`reward_overrides`, `rewards`), MLflow tag `recompensa`. Defaults = v1/v2 values | `docs/ambiente-v0.3.md` |
| `warehouse-v4` (0.4.0) | `env/warehouse-v4` -> `1b82ca9` | `distance` term (state penalty: coefficient x Manhattan distance to the previous target, per step, <= 0). Open map `configs/layout_v0.5.json` (no interior wall, no closable gap), level `m1o`, `Layout.validate_routes` only demands that the blockable gap alters a route when a gap exists | `docs/ambiente-v0.4.md` |
| `warehouse-v5` (0.5.0) | `env/warehouse-v5` -> `2b80031` | `manhattan_progress` (>= 0, **difference** of Manhattan distance to the same target before/after the step; no jump when the target changes) and `height_mismatch` (<= 0, per step and per tray position of mismatch, only while standing on an interaction cell of the current target; needed position is 0 at dispatch). Both default 0 | `docs/ambiente-v0.5.md` |

v2 models share observation and actions with v3-v5 and load there (trained without the new terms). **v1 models are incompatible** (22 inputs, 5 outputs); keep them as history only.

## Current contract (v5), summary

- **Code:** `envs/` (`env.py` base, `missions.py` = `MakeupMissionEnv`, `inventory.py`, `handling.py` tray config, `layout.py`, `rewards.py`). Factory: `envs.make_env(blocked, layout_path, orders, reward_overrides, **kw)`. With `orders=N`: each episode draws N distinct SKUs of 1 unit and restocks the inventory on reset. `reset(seed=s)` reproduces the order; `reset()` draws it from the env RNG.
- **Observation `Box(27)`, all in [0,1]:** 0-7 rays (8 m range), 8-9 own (x,y), 10-11 target (x,y) (station cell of the rack E01-E06 or `DELIVERY`), 12-15 orientation one-hot, 16 moving, 17 battery, 18 carried/capacity, 19-21 stage one-hot (recoger/entregar/completada), 22 time left, 23 order progress, 24 facing an interactable, 25 tray elevation, 26 target elevation. **Not given:** map, SKU/level/quantity, inventory, tray phase, action mask, reward.
- **Actions `Discrete(8)`:** 0 AVANZAR, 1 GIRAR_IZQUIERDA, 2 GIRAR_DERECHA, 3 FRENAR, 4 CARGAR, 5 DESCARGAR, 6 SUBIR, 7 BAJAR. One tray position per SUBIR/BAJAR: positions 0.55 (travel) / 0.99 / 1.79 / 2.60 m, so shelf level 3 needs 3 SUBIR from stowed. SUBIR from stowed needs: stopped, facing the target rack, stage recoger. CARGAR needs: stopped, facing, tray exactly at the line's height. DESCARGAR needs: stopped, at the dispatch access cell (21,16) facing east, tray stowed. With the tray up, AVANZAR/GIRAR are blocked (no invalid penalty, counted in `blocked_lift_moves`). The tray stays up after CARGAR; the agent must BAJAR. Costs: advance 0.8, turn 0.2, brake 0.1, CARGAR/DESCARGAR 0.2, SUBIR/BAJAR 0.1 + 0.8 per metre of travel.
- **Episode:** `terminated` = `success` | `battery_depleted` | `unreachable_target` | `insufficient_budget`; `truncated` = `time_limit` (400 steps). Battery 180.
- **Maps:** `layout_v0.4.json` (walled, 25x19, interior wall y=14 with a permanent gap at x=20 and a closable gap at x=6, dispatch conveyor (22,16)-(23,16), approach (21,16)); `layout_v0.5.json` (same without the interior wall). BASE (3,16) facing north.
- **Reward (defaults; `e4l` values in brackets):** pickup +10, delivery +30, completion +50, progress +0.3 x BFS-distance reduction, time -0.1, battery -0.02 x units, collision -5 [-1], invalid interaction -2 [-0.2], distance 0 (v4 term), manhattan_progress 0 [0.3], height_mismatch 0 [-0.02]. Milestones pay once per line; delivery pays once per DESCARGAR; every penalty is <= 0, so repeating invalid actions or SUBIR/BAJAR loops never profits (tested). Components appear in `info["reward_components"]`.
- **Reward comparability:** returns only compare between runs with identical coefficients. Across reward sets compare success rate, pickups, deliveries, steps.

## References measured on the walled/open maps (3 random SKUs)
Random: 0%. Rule-based heuristic (`pipelines/baselines.HeuristicPolicy`, BFS + SUBIR/CARGAR/BAJAR/DESCARGAR sequence): 100%, 76-105 steps on the walled map, about 71 on the open map; idle (FRENAR for 400 steps) returns about -41.

## Plan layout rule (never change)
The PDF plan's structure wins: `envs/ configs/ pipelines/ tests/ web/ manifests/ docs/ api/`. Angie's `src/warehouse_rush/` layout was relocated into it (imports: `warehouse_rush.env` -> `envs.env`, `.policies` -> `pipelines.baselines`, `.cloud` -> `api._cloud`, `.viewer` -> `api._viewer`, `.train` -> `pipelines.train`).
