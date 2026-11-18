# Warehouse Rush: environment spec (design sheet 04)

Source: "MLOps Autonomous Lab / Guía de diseño 04" (teaching design sheet, 23 Oct 2026, scope per team, 4 weeks, no measured performance). The original PDF covers six environments; **we only build Warehouse Rush**. Ignore Autonomous Rally, Rocket Landing, Robot Expedition, Drone Rescue and Autonomous Parking.

The sheet is a *proposal*: ranges, units and values are "propuestas por calibrar". Define and document them ourselves, and do not invent numbers as if they came from the sheet.

## Goal
Complete a sequence of orders: pick up packages and deliver them at the correct station.

## World
Flat warehouse floor: shelving racks + aisles + **two pickup stations** (Recogida 1, Recogida 2) + **one delivery station** (Entrega). A closable aisle (barrier) is used for the incident scenario. Mobile robot with differential-style drive (advance + turn), carrying at most the current package.

Physics and rules live in the simulator, not in the rendering: graphics only show the same state. Keep `step()` logic independent of `render()`.

## State (internal)
Position, orientation, velocities, current order, load (carrying or not), battery, time, deliveries completed.

## Observation
Obstacle rays, relative goal (direction/distance to current objective), velocity, battery, load, stage, remaining time. Use a `Box` with normalised values; document the layout and ray count (the sheet does not fix it).

## Action
Advance, turn, and an interact action (pick up / deliver). Interact is only valid **near a station (within interaction radius) and at low speed**. Interact outside those conditions is an *invalid interaction* and is penalised. Suggested: `Box` for advance/turn in [-1, 1] plus a discrete/binary interact component (e.g. `Dict` or `MultiDiscrete`-compatible design); decide and document.

## Parameters (configure before running; define ranges + units)
| Parameter | Unit | Effect |
|---|---|---|
| Aisle width | m | circulation margin |
| Interaction radius | m | proximity needed to pick/deliver |
| Speed when loaded | m/s | effect of the package |
| Number of orders | count | mission length |

Expose these via the env constructor / options so experiments can vary one at a time.

## Reward
Reward correct deliveries and progress. Penalise time, energy, collisions and invalid interactions.

## Episode success
All assigned orders completed within the time and battery limits. Terminate on success; truncate on time limit; decide whether battery depletion / collision terminate.

## Evaluation metrics
Orders delivered, time per order, energy consumption, collisions, invalid interactions.

## Changing conditions (incident)
Closure of an aisle. Evaluate alternative routes **without changing the orders**. Change one condition per experiment.

## Team challenge: reward hacking
"Can it score by picking up and dropping the same package?" The reward must make this unprofitable: pay only for a *valid* delivery of the *current* order at the *correct* station, once, and reward progress as potential-based or one-shot milestones so cycles cannot be farmed. Write a test that tries this loop and asserts net reward is not positive.

## Deliverables of the first session ("HOY")
Draw the map, define ranges, and hand-simulate **five transitions** following:
observation → action → physics → reward → new observation.

## Working conventions
- Python venv at `.venv` (gymnasium installed). Experiments on branches, e.g. `experiment-1`.
- Subclass `gymnasium.Env`; implement `reset(seed=, options=)`, `step`, spaces; validate with `gymnasium.utils.env_checker.check_env`.
- Seeded and deterministic given a seed, so experiments are comparable.
- The original PDF is gitignored; do not commit it.
