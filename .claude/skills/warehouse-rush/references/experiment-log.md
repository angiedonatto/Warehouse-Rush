# Experiment log (R2) and what we learned

Status: 2026-11-14. Full evidence, per-episode CSV/JSON and manifests are in the repo: `docs/experimentos.md` (Spanish, hypotheses written **before** training), `docs/resultados/eval/<run>/`, `docs/resultados/training/<run>/`, `manifests/<run>.json`, MLflow (`warehouse-n1`, `warehouse-m1`, `warehouse-m1o`; local `mlflow.db`, not committed). Run names: `<nivel>-<id>-seed<seed>`.

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
Mean 31.3% vs e4l 30.7% (+0.7 pp < 5 pp): hypothesis rejected. Findings: seed 1 is bit-identical to e4l-seed1 (never loads, so a milestone after the last pickup is never paid: it cannot help seeds that never load). seed 2 went from 2 to 268 training successes but still spins with cargo under the deterministic policy (turns about 0.24 each vs AVANZAR about 0.01 after loading): the stochastic policy completes the leg, the argmax one does not. seed 0 successes take 72.4 steps (e4l 71.8). Next: more seeds for e4l/g1, a signal before the pickup (for seeds like 1).
**Stochastic follow-up (post hoc, `scripts/eval_stochastic.py`):** g1-seed2 completes the mission 94/94/94% when sampling actions (e4l-seed2 about 1%), seed 0 96% for both, seed 1 0%. So the milestone worked on seed 2 but argmax evaluation hides it (turn and AVANZAR probabilities are close after loading). Successes of g1-seed2 take 108-119 steps (not faster). The official verdict stays `rechazado` (deterministic criterion fixed beforehand); a stochastic criterion would have to be pre-registered for a new comparison with unseen eval seeds.

## Behaviour cloning (h0) + PPO fine-tuning (h1), `pipelines/bc.py`, 3 seeds, no env/reward change (v7, e4l reward)
| Run | What | Success | Steps of successes | Collisions/ep | Status |
|---|---|---:|---:|---:|---|
| `m1o-h0-seed0/1/2` | imitate the heuristic only (1000 episodes, half with 25% action noise; labels = heuristic action at that state; critic regressed on returns) | 100 / 100 / 100% | 71.3 | 0 | candidate (reference, not recommended) |
| `m1o-h1-seed0` | PPO 600k from h0-seed0 with the e4l PPO + reward | 88% | 74.8 | 6.74 | rejected (criterion) |
| `m1o-h1-seed1` | same, seed 1 | 92% | 110.7 | 0 | rejected |
| `m1o-h1-seed2` | same, seed 2 | 100% | 79.8 | 0 | rejected |
Criterion (pre-registered, h1 vs e4l): mean success +62.7 pp (93.3% vs 30.7%) but mean collisions 2.25/ep vs limit +0.1 over 0 -> rejected (both conditions required; all excess collisions from seed 0). Findings: (1) imitation alone solves the task on every seed, so the 27-dim observation is sufficient; e4l/g1 were limited by discovering the task, not by capacity. (2) PPO fine-tuning with the e4l config DEGRADES the imitator from the first checkpoint (dev-eval return 127 -> 6 / 1 / -19 at 20k steps) and oscillates for 600k steps; the final model is only wherever training stopped. Probable cause (untested): critic explained variance only 0.38-0.40 plus lr 3e-4 and ent_coef 0. (3) Stochastic diagnostic on seeds 20000-20049: h1 100% on all seeds. (4) h0 copies a privileged controller: a reference, not RL evidence; the team must decide how to present it. Next: fine-tuning that keeps the policy (lr 3e-5, critic warm-up with frozen actor, target_kl) and also evaluate `models/<run>/best`. BC hyperparameters may be tuned only on validation accuracy (rule fixed beforehand), never on the suite. Demos regenerate deterministically (about 8 min; they are identical for every seed, so a cache would save 10 min per run).

## Cancelled: seeds 3-7 of e4l and g1 (pre-registered, never evaluated)
Configs `m1o_{e4l,g1_hito}_seed{3..7}.yaml` and a criterion (mean of the 5 new seeds, deterministic eval, g1 >= e4l + 5 pp, collisions <= +0.1/ep) were committed before training. The g1 runs were stopped at about 300 000 of 606 208 steps (user switched to behaviour cloning); the e4l runs never started. Status `interrumpido` in MLflow, no evaluation, partial folders untracked. The criterion was never applied; do not read the missing results as a null result.

## Lessons (use these when designing the next experiment)
1. The bottleneck is a **missing positive signal before the first delivery**, not exploration cost or algorithm (PPO, DQN, entropy sweep 0-0.1 and penalty sweeps all failed alike). Behaviour cloning confirmed it: a network of the same size and the same 27-dim observation imitates the heuristic to 100% success on every seed.
2. Shaping must keep **pick-up the best move**: a per-step state penalty that jumps when the target changes inverts the incentive. Use differences measured against the same target.
3. A penalty applied only in the zone the agent must occupy creates an **avoidance zone** (-0.05, -0.1). Check scripted returns of "approach and idle" vs "idle at base" **before** training.
4. **Budget matters**: success appeared after about 1.7x the original budget; judge a reward with at least about 600k steps.
5. **Seed variance is huge** (e4l 92/0/0, g1 94/0/0, h1 88/92/100 only because of the BC start). Never conclude from one seed; a reward term that acts after loading cannot help a seed that never loads (g1-seed1 was bit-identical to e4l-seed1).
6. Always run a **control with the same budget** and the same code; training is deterministic (same seed -> same model), so a re-run of a finished config is wasted compute, and bit-identical results show a term never fired.
7. Return does not measure progress (e4's return -70.5 was worse than the control's while its behaviour was more advanced); report success, pickups, deliveries, invalid interactions, steps, collisions.
8. The common failure after loading is **not completing the trip with the tray down** (tray never lowered, or loaded but never delivered, or spinning in place with cargo). A bonus for lowering the tray (v6) made the agent lower it but not drive; a delivery-leg milestone (v7) helped one seed.
9. **Argmax evaluation can hide a working policy.** When action probabilities after loading are spread (turn 0.24 vs AVANZAR 0.01), the deterministic policy loops while the sampled one completes the mission (g1-seed2 0% vs 94%). Report sampled eval as a diagnostic; making it the criterion needs a new pre-registered criterion with unseen seeds.
10. **Raising `time` penalty does not shorten successful episodes** (they already last as long as the heuristic, about 71-73 steps); the long mean episode length came from failures. It can reduce success (f2: 92% -> 44% on seed 0).
11. **PPO fine-tuning with the e4l config destroys a good starting policy** (dev-eval return 127 -> about 0 at 20k steps, then oscillates for 600k): critic explained variance after BC is only 0.38-0.40, lr 3e-4 and ent_coef 0. A final model is only the point where training stopped; compare against `models/<run>/best` too.
12. A pre-registered **two-part criterion** is applied as written even when one part is overwhelmingly met (h1: +62.7 pp success but collisions failed). State both numbers.
13. Behaviour cloning from a privileged expert gives a strong reference but is not RL evidence; label it that way (`candidato`, reference, not recommended) and let the team decide how to present it.

## Open items / next candidates (none started)
1. **Fine-tuning that keeps the BC policy**: lr 3e-5, critic warm-up with the actor frozen for the first steps, or `target_kl`; pre-register, 3+ seeds; also evaluate the saved `best` checkpoint of the periodic eval.
2. Decide with the team whether h0 (copy of the heuristic) is an acceptable result or only a reference; if a stochastic evaluation is wanted, pre-register that criterion and use unseen eval seeds (20000-20049 were used for diagnostics only).
3. More seeds of `e4l` and `g1` (3-7), configs already exist (cancelled, see above).
4. A signal **before** the first pickup for seeds that never load (for example a one-off bonus for reaching the first rack's interaction cell) - new version.
5. Observation with the target relative to the robot's heading (egocentric), and randomized start poses (curriculum) - new env version.
6. The e4 reward on the walled map (`layout_v0.4.json`).
7. Cache the BC demonstrations by config hash (about 8 of the 10 minutes per BC run are demonstration generation).
8. Missing from the plan: finalists x 3 seeds comparison, `compare.py`, `callbacks.py`, suite-driven `evaluate.py`, N3 incident suite for v2+ (the open map has no closable gap; the walled map still has one at (6,14)), `test-final` run, Prefect flow, FastAPI, DVC/MLflow remotes, web viewer rebuilt and tested against v2-v7, push to origin and PR to `main`.
