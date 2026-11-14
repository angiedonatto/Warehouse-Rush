# Experiment log (R2) and what we learned

Status: 2026-11-13. Full evidence, per-episode CSV/JSON and manifests are in the repo: `docs/experimentos.md` (Spanish, hypotheses written **before** training), `docs/resultados/eval/<run>/`, `docs/resultados/training/<run>/`, `manifests/<run>.json`, MLflow (`warehouse-n1`, `warehouse-m1`, `warehouse-m1o`; local `mlflow.db`, not committed). Run names: `<nivel>-<id>-seed<seed>`.

Everything uses PPO `MlpPolicy` [64,64], lr 3e-4, `n_steps` 2048 x `n_envs` 4, batch 64, 10 epochs, gamma 0.99, gae_lambda 0.95, clip 0.2, `ent_coef` 0.0 (the C0 config) unless stated. Budget 200 000 requested (204 800 effective = 25 x 8 192) unless stated; 600 000 requested = 606 208 effective. Evaluation: frozen model, deterministic actions, 50 episodes, seeds 10000-10049 (`suite-n1-v1`, `suite-m1-v1`, `suite-m1o-v1`), 1 training seed unless stated.

## warehouse-v1 (history, N1 = 1 order)
| Run | Change | Success | Status |
|---|---|---:|---|
| `experiment-001` | PPO, 20 000 steps | 0% (FRENAR every step) | history |
| references | random / rule (BFS) | 0% / 100% | reference |
| `n1-c0-seed0` | baseline PPO | 0% | candidate |
| `n1-c1`, `c1b`, `c1c` | `ent_coef` 0.01 / 0.05 / 0.1 | 0% each | rejected |
| `n1-c6-seed0` | DQN instead of PPO | 0% | rejected |
Diagnosis then: policy collapses to standing still; random exploration cost about -265/episode vs -25.5 idle; zero training successes.

## warehouse-v2 / v3 (walled map v0.4, level `m1`, 3 random SKUs per episode)
| Run | Reward change vs default | Success | Idle (FRENAR) in eval | Status |
|---|---|---:|---:|---|
| `m1-c0-seed0` (v2) | none | 0% | 93.4% | candidate (baseline) |
| `m1-c0b-seed0` (v3) | none; control, reproduces `m1-c0` exactly | 0% | 93.4% | candidate (control) |
| `m1-r1/r2/r3` | invalid -1 / -0.2 / -0.05 | 0% | 98.5 / 99.2 / 98.3% | rejected |
| `m1-r4/r5/r6/r7` | invalid -0.2, collision -2 / -1 / -0.5 / -0.1 | 0% | 97.3 / 98.2 / 84.6 / 94.4% | rejected |
Findings: of the ~-518 return of a random episode, invalid interactions were 77% (199.6 x -2), collisions 15%, time/battery 8%. Cheaper exploration (first-10-episode return -503 -> -83) did **not** produce learning: PPO still converges to idling because no explored behaviour earns a positive signal. At collision -0.5/-0.1 a wall-bumping trap appears (eval seed 10033: 199 and 219 collisions until battery ran out). Do not lower penalties further.

## warehouse-v4 (open map v0.5, level `m1o`; collision -1, invalid -0.2 fixed)
| Run | `distance` (state penalty) | Success | Episodes with a pickup | Status |
|---|---:|---:|---:|---|
| `m1o-c0-seed0` (control) | 0 | 0% | 7/50 | candidate |
| `m1o-d1/d2/d3` | -0.005 / -0.01 / -0.02 | 0% each | 0 each | rejected |
Findings: the open map alone (vs walled `m1-r5`, same coefficients: 0 pickups, 98% idle) already lets the control reach the first rack in 48/50 episodes (median step 12) and complete navigate-stop-SUBIR-CARGAR in 7/50; it never lowers the tray (BAJAR 1 time in 2 636 steps after loading) and stalls. **The state-based distance term made picking up the first item worse than approaching and idling** (scripted returns, 20 seeds: `distance` -0.02 -> approach+idle -47.1 vs pick+stall -106.7), because after the pickup the target jumps about 10 cells away while the raised tray locks the robot. d2/d3 turn in place next to the rack instead of pressing SUBIR (SUBIR probability 0.26 / 0.001).

## warehouse-v5 (open map; collision -1, invalid -0.2; `manhattan_progress`, `height_mismatch`)
200 000-step runs, seed 0 (all vs control `m1o-c0`, all rejected by criterion):
| Run | manhattan_progress | height_mismatch | Success | Pickups/ep | Behaviour |
|---|---:|---:|---:|---:|---|
| `m1o-e1` | 0.3 | 0 | 0% | 0.00 | reaches rack, raises tray once, then CARGAR spam (26.6 invalid/ep) or brakes |
| `m1o-e2` | 0 | -0.1 | 0% | 0.00 | 0/50 reach an interaction cell; spins near base (**avoidance**) |
| `m1o-e3` | 0.3 | -0.1 | 0% | 0.00 | stops about 3 cells short of the rack (**avoidance**) |
| `m1o-e4` | 0.3 | -0.02 | 0% | 0.30 | most advanced: loads in 12/50, lowers tray in 6/50, 1/512 training episode with 3 deliveries; 159 invalid/ep |
| `m1o-e5` | 0.3 | -0.05 | 0% | 0.00 | walks halfway to the rack and brakes (**avoidance**) |
Findings: a height penalty applied only on the interaction cell punishes standing exactly where the agent must be. Measured before training (scripted, 10 seeds): approach+idle costs -49.5 / -70.6 / -105.8 at -0.02 / -0.05 / -0.1 vs -40.8 idling at base; policy avoided the rack at -0.05 and -0.1 only. The useful range sits between -0.02 and -0.05 (two data points).

## e4 reward with 3x the budget (606 208 steps), 3 seeds, same-budget control
| Run | Seed | Success | Deliveries/ep | Pickups/ep | Training episodes with 3 deliveries | Status |
|---|---:|---:|---:|---:|---:|---|
| `m1o-e4l-seed0` | 0 | **92%** (46/50) | 2.76 | 2.92 | 2 395 / 3 278 | candidate (first model to complete the mission) |
| `m1o-e4l-seed1` | 1 | 0% | 0.00 | 0.00 | 0 / 1 512 | candidate (evidence) |
| `m1o-e4l-seed2` | 2 | 0% | 0.00 | 2.42 | 2 / 1 515 | candidate (evidence) |
| `m1o-c0l-seed0` (control, no v4/v5 terms) | 0 | 0% | 0.00 | 1.68 | 0 / 1 513 | candidate (control) |
- Pre-registered criterion (mean success of 3 seeds >= control + 5 pp, collisions not up >10%): **met** (30.7% +- 43.4 pp, population std; control 0%). It is carried by **one seed of three**; all e4l runs stay `candidato`, none `recomendado` (the course requires finalists, more seeds and the reserved final test; registering a candidate is not promoting it).
- Seed 0 fails (4/50) holding 2 items with the tray up. Seed 1 collapses to spamming DESCARGAR (64.6% of steps, 258 invalid/ep) and reaches the rack in 10/50. Seed 2 loads about 2.4 items but never delivers and spins. The control with 3x steps also learns to load (1.68/ep) but never delivers: more steps alone gave pickups, the e4 reward gave deliveries.
- **Learning curve of `e4l-seed0`** (`docs/resultados/eval/m1o-e4l-seed0-curve.json`, checkpoints every 20 000 steps): 0% until about 120 000 (idle), about 200 000 explores with 156 invalid/ep and 0.06 pickups, first success **340 000 (10%)**, 76% at 480 000, about 88-94% from 500 000 (irregular, 78% at 540 000). The original 200k budget stops halfway (learns to load, not to deliver). Do not choose checkpoints from this curve (the suite is the comparison suite).

- **What the working policy looks like** (`scripts/trace_policy.py m1o-e4l-seed0`, 6 episodes): in the key states it is near-deterministic: stopped facing the rack with the tray down -> SUBIR 0.96; tray below the needed height -> SUBIR 0.94; tray at the needed height -> CARGAR 0.94; after loading with the tray up -> BAJAR 0.70 (CARGAR 0.25 when another line is on the same rack). The failing runs were near-uniform in those states (for example CARGAR 0.12-0.34 vs competing turns/brakes).

## warehouse-v6: time -0.2 and `lower_bonus` 1.0 (600k steps; controls = e4l)
| Run | time | lower_bonus | Seed | Success | Pickups/ep | Deliveries/ep | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| `m1o-f1-seed0/1/2` | -0.2 | 1.0 | 0/1/2 | 0 / 0 / 0% | 2.50 / 0.82 / 0.00 | 0 | rejected |
| `m1o-f2-seed0` (ablation) | -0.2 | 0 | 0 | 44% | 2.70 | 1.32 | rejected (criterion: -48 pp vs e4l-seed0) |
| `m1o-f3-seed0` (ablation) | -0.1 | 1.0 | 0 | 0% | 2.38 | 0 | rejected |
Findings: (1) e4l-seed0's successful episodes already take 71.8 steps (heuristic 71.3); the long mean (95) came from 4 failures (3 time_limit at 400 steps). (2) The bonus does what it targets (f1-seed0 and f3 raise, load and lower the tray in 50/50) but the policy then spins instead of driving to the dispatch (0 deliveries in about 7 600 training episodes of f1/f3). The bottleneck moved to the leg with cargo to the dispatch. (3) time -0.2 alone did not shorten successes (73.6 steps) and cut success 92% -> 44% (seed 0). (4) f1 seeds 1 and 2 reproduce the e4l-seed1/2 failures. Scripted returns before training showed no new perverse incentive at -0.2, so the loss is not an avoidance trap of that kind. Do not raise `time` further; next idea: a milestone for progress with cargo toward the dispatch, and more e4l seeds first.

## warehouse-v7: `carry_milestone` 5.0 (600k steps, 3 seeds; control e4l; lower_bonus removed, time back to -0.1)
| Run | Seed | Success | Pickups/ep | Deliveries/ep | Training successes | Status |
|---|---:|---:|---:|---:|---:|---|
| `m1o-g1-seed0` | 0 | 94% | 2.94 | 2.82 | 2 184 / 3 120 | rejected (mean criterion) |
| `m1o-g1-seed1` | 1 | 0% | 0.00 | 0 | 0 / 1 512 | rejected |
| `m1o-g1-seed2` | 2 | 0% | 2.44 | 0 | 268 / 1 673 | rejected |
Mean 31.3% vs e4l 30.7% (+0.7 pp < 5 pp): hypothesis rejected. Findings: seed 1 is bit-identical to e4l-seed1 (never loads, so a milestone after the last pickup is never paid: it cannot help seeds that never load). seed 2 went from 2 to 268 training successes but still spins with cargo under the deterministic policy (turns about 0.24 each vs AVANZAR about 0.01 after loading): the stochastic policy completes the leg, the argmax one does not. seed 0 successes take 72.4 steps (e4l 71.8). Next: more seeds for e4l/g1, evaluate g1-seed2 with a stochastic policy, a signal before the pickup (for seeds like 1).

## Lessons (use these when designing the next experiment)
1. The bottleneck is a **missing positive signal before the first delivery**, not exploration cost or algorithm (PPO, DQN, entropy sweep 0-0.1 and penalty sweeps all failed alike).
2. Shaping must keep **pick-up the best move**: a per-step state penalty that jumps when the target changes inverts the incentive. Use differences measured against the same target.
3. A penalty applied only in the zone the agent must occupy creates an **avoidance zone** (-0.05, -0.1). Check scripted returns of "approach and idle" vs "idle at base" **before** training.
4. **Budget matters**: success appeared after about 1.7x the original budget; judge a reward with at least about 600k steps.
5. **Seed variance is huge** (92 / 0 / 0). Never conclude from one seed; the course asks for 3 seeds for finalists.
6. Always run a **control with the same budget** and the same code; training is deterministic (same seed -> same model), so a re-run of a finished config is wasted compute.
7. Return does not measure progress (e4's return -70.5 was worse than the control's while its behaviour was more advanced); report success, pickups, deliveries, invalid interactions, steps.
8. The common failure after loading is **not completing the trip with the tray down** (tray never lowered, or loaded but never delivered).

## Open items / next candidates (none started)
1. Replicate `e4l` on more seeds (for example 3-7) at 606 208 steps to estimate how often it works; also e4 on seeds 1-2 at 200k if the team wants the literal budget comparison.
2. Run the e4 reward on the **walled map** (`layout_v0.4.json`); the earlier "walled run if favorable" condition was never triggered for the distance term, but e4l-seed0 now makes it relevant.
3. Once-per-line bonuses (reaching the right tray height, lowering after loading, arriving at the conveyor with the tray down) = new version `warehouse-v6`.
4. Behaviour cloning from the heuristic then PPO fine-tuning (demonstrations via DVC).
5. A penalty/reward between -0.02 and -0.05 is not worth more runs; rewarding correct height instead of punishing wrong height would be a new version.
6. Missing from the plan: finalists x 3 seeds comparison, `compare.py`, `callbacks.py`, suite-driven `evaluate.py`, N3 incident suite for v2+ (the open map has no closable gap; the walled map still has one at (6,14)), `test-final` run, Prefect flow, FastAPI, DVC/MLflow remotes, web viewer rebuilt and tested against v2-v5, push to origin and PR to `main`.
