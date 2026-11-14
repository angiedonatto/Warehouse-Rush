# R2 · Training and experiments (guide of 4 Nov 2026)

> **Status as of 2026-11-13:** this file is the original guide. The environment moved on (v5, makeup mode, `Box(27)`/`Discrete(8)`, levels `m1`/`m1o`) and the hypotheses C1-C4 below were not run as written (C0/C1/C6 ran on v1 and were rejected; later work used reward sweeps). What was actually run, results and lessons: [experiment-log.md](experiment-log.md); how to run and document: [workflow.md](workflow.md).

R2 turns the env into evidence: trains PPO agents, compares them to references on a fixed suite, and decides with data which model is adopted, rejected, or restored. Weight: 25%. Done when every learning claim in the report traces to a run, a suite and a seed. All numbers below are initial proposals: measure and adjust, agree thresholds as a team, and **do not change them after seeing results**.

## Own files
`configs/experiments/`, `configs/suites/`, `configs/criterios.yaml`, `pipelines/{train,evaluate,baselines,callbacks,compare}.py`, `docs/experimentos.md`, `docs/resultados/comparacion-<fecha>.md`.
Depends on: R1 contract + env (minimal first) + `envs/heuristica.py`; R3 `pipelines/tracking.py`.

## Deliverables
1. Random and rule references + PPO baseline per level. 2. Fixed versioned eval suite with per-episode results. 3. At least four hypothesis configs, each with a MLflow run (including worse/failed). 4. Two finalists x 3 training seeds. 5. N3 incident degradation and intervention. 6. `docs/experimentos.md`.

## References (tag `tipo=referencia`, same suite)
- Random: random each action component (`MultiDiscrete([3,3,2])` per guide; reconcile with the contract). Floor.
- Rule: R1's controller (turn to goal, brake on arrival, interact, avoid with rays). Reasonable ceiling without learning.
- Learned baseline: PPO with initial config.

## Initial PPO config
`MlpPolicy` net `[64,64]` (separate actor/critic), lr 3e-4, `n_steps` 2048 x `n_envs` 4 (`DummyVecEnv`), batch 64, n_epochs 10, gamma 0.99, gae_lambda 0.95, clip_range 0.2, ent_coef 0.0, device cpu. Change one value per hypothesis. Observation is already normalized by the env; if `VecNormalize` is used, save and register its stats with the model or the model is not recoverable.

## Budget (env steps, equal for every compared candidate)
| Level | Steps | Intermediate eval |
|---|---|---|
| N1 | 200,000 | every 20,000 steps, 10 episodes |
| N2 | 1,000,000 | every 50,000, 10 episodes |
| N3 (intervention) | +300,000 from the N2 checkpoint | every 50,000, 10 episodes |
Time the first N1 run on your machine; report effective steps and minutes per run and in the final report.

## Suites (`configs/suites/`)
| Suite | Episodes | Seeds | Use |
|---|---|---|---|
| `dev-n1-v1`, `dev-n2-v1`, `dev-n3-v1` | 10 | 1000-1009 | intermediate eval during training |
| `suite-n1-v1`, `suite-n2-v1`, `suite-n3-v1` | 50 | 10000-10049 | compare candidates, pick finalists |
| `test-final` | 100 | reserved, outside public repo | once, at the end, nothing tuned afterwards |
Always: frozen model, deterministic actions, same suite. Per-episode metrics in `evaluacion.json`: success + end cause (success/battery/collisions/time), orders delivered, time per order, battery use %, collisions and invalid interactions, return (only within same env+reward), inference latency ms.

## Selection criteria (`configs/criterios.yaml`, fixed before seeing results)
1. Adopt if success rate beats current baseline by >= 5 percentage points on the level suite. 2. And collisions per episode do not rise more than 10%. 3. Tie on success: lower time per order wins. 4. Otherwise reject, but keep run and evidence with status `rechazado`.

## Hypotheses (one dimension changed each; write hypothesis before training)
| Id | Level | Change | Hypothesis | Compared to |
|---|---|---|---|---|
| C0 | N1 | baseline | - | random and rule |
| C1 | N1 | `ent_coef` 0.0 -> 0.01 | more exploration raises N1 success at same budget | C0 |
| C2 | N2 | `gamma` 0.99 -> 0.995 | 3-order episodes need far rewards: fewer truncated episodes | N2 baseline |
| C3 | N2 | continue from N1 checkpoint (`parent_run_id`) | same N2 success with fewer steps | N2 baseline from scratch |
| C4 | N3 | retrain N2 model with random closed aisle | recovers success lost to the incident without forgetting N2 | N2 model evaluated in N3 |
Main contrast: **C2 vs C3 on N2**; they are the two finalists.

## Finalists, seeds, final test
Train each finalist with seeds 0, 1, 2 (same budget, six independent runs). Evaluate all on `suite-n2-v1` (eval seeds never mixed with training seeds). Report mean and std per metric across the 3 seeds plus each seed. Show training curve (with exploration) and deterministic eval curve **separately**. Apply `criterios.yaml`: winner `recomendado`, other `rechazado` with evidence. Run `test-final` once on the chosen model. A run failing before weights is logged `fallido` + diagnosis + "sin checkpoint disponible".

## Incident (N3)
Take the recommended N2 model, evaluate on `suite-n2-v1` and `suite-n3-v1` with same seeds, record degradation per metric and per end cause. Train C4 from that checkpoint; compare C4 vs original on N3 and on N2 (forgetting check). Decide accept/reject the intervention; keep the candidate either way.

## What to log in MLflow (via R3's `tracking.py`)
Before training: resolved config + SHA-256, hypothesis, level, seed, budget (params, `config.json`); tags `git_commit`, `environment_version`, `parent_run_id`, `tipo`. During: `train/*` and `eval/{exito,entregas,choques,tiempo_pedido}`. On close: final model + selected checkpoints, `evaluacion.json`, real steps/minutes, status (`candidato`/`recomendado`/`rechazado`/`fallido`/`interrumpido`). Experiments `warehouse-n1/n2/n3`; run names like `n2-c3-seed1`. Save best checkpoint by success and the final one.

## Planned layout
```
configs/experiments/ c0_baseline_n1.yaml c1_entropia_n1.yaml c2_gamma_n2.yaml c3_continuacion_n2.yaml c4_pasillo_n3.yaml
configs/suites/ dev-n1-v1.yaml suite-n1-v1.yaml ...
configs/criterios.yaml
pipelines/ baselines.py train.py (--config) evaluate.py callbacks.py compare.py
docs/experimentos.md
```
Example config keys: `id, hipotesis, nivel, environment_version, parent_run_id, seed, presupuesto_pasos, ppo{learning_rate,n_steps,n_envs,batch_size,n_epochs,gamma,gae_lambda,clip_range,ent_coef,net_arch}, evaluacion{intermedia,cada_pasos,final}`.

## Prompts per phase (paste into Claude Code, ask for a plan first, review every diff)
- **Phase 0 refs + eval**: read `envs/CONTRATO.md`; create `pipelines/baselines.py` (random on `MultiDiscrete([3,3,2])`, rule policy using `envs/heuristica.py`, both with `predict(obs, deterministic)`); `pipelines/evaluate.py` takes policy or run_id + suite, runs seeded episodes, writes `evaluacion.json` (success, end cause, deliveries, time/order, consumption, collisions, invalid, return, latency per episode + summary); tests with the minimal env.
- **Phase 1 traceable training**: `pipelines/train.py --config ...yaml`; validate YAML; 4 envs with `DummyVecEnv` and config seed; SB3 PPO CPU; log via `tracking.py` params, tags (git_commit, environment_version, config_sha256, nivel, hipótesis, parent_run_id), final model, status; if `parent_run_id` load checkpoint and check env-version compatibility; on failure mark run failed with error.
- **Phase 2 curves**: `pipelines/callbacks.py` evaluating the frozen model every N steps on the level's dev suite, deterministic, logging `eval/exito, eval/entregas, eval/choques, eval/tiempo_pedido`; training metrics prefixed `train/`; keep best (by success) and final checkpoint; integrate in `train.py`.
- **Phase 3 N1 baselines**: run random, rule and C0 on `suite-n1-v1`, show comparison table, note real training time and whether the budget is enough in `docs/experimentos.md`.
- **Phase 4 hypotheses + finalists**: YAMLs C1-C4 (one dimension each, hypothesis written); `pipelines/compare.py` from run_ids -> load `evaluacion.json`, mean/std per config across seeds, apply `criterios.yaml`, write `docs/resultados/comparacion-<fecha>.md` with table, decision and separate PNG curves.
- **Phase 5 incident**: evaluate recommended N2 on `suite-n2-v1` and `suite-n3-v1`, record degradation by metric and cause, train C4 from that checkpoint, compare C4 vs original on N3 and N2, write decision in `docs/experimentos.md`.
- **Defense prep**: explain each hypothesis, result and why accepted/rejected from `docs/experimentos.md`; ask five hard questions on seeds, budget, comparability.

## Coordination
R1: receive contract, env, rule controller; warn R1 if reward permits exploits found during training (phase 0 on). R3: use `tracking.py` and manifest format; hand over `run_id`s of selected models and the criteria (phase 1 and when choosing finalists). R4: hand over metrics and curves as JSON (phase 4).

## Checklist
- [ ] Random and rule refs evaluated on the three suites
- [ ] PPO baseline per level in MLflow
- [ ] C1-C4: hypothesis written before training, run registered
- [ ] Failed, interrupted, rejected runs kept with status
- [ ] Two finalists x 3 seeds + comparison
- [ ] Training and eval curves separate
- [ ] N3 degradation measured, intervention decided
- [ ] `test-final` run once
- [ ] `docs/experimentos.md` with real budget (steps and minutes) per run
- [ ] Can explain in defense why return != success rate
