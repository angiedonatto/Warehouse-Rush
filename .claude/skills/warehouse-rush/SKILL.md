---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract and its versions warehouse-v1 to v10, behaviour cloning from the heuristic (pipelines/bc.py), the full experiment log (what was tried, what worked, what failed and why), how to run/evaluate/diagnose/document an experiment, reward-hacking checks. The user is R2 (Entrenamiento y experimentos) and has also been changing the environment on the team's instruction.
---

# Warehouse Rush: MLOps final project

Sources (PDFs in Windows Downloads, read 2026-11-06): course brief `Enunciado-proyecto-final-MLOps.pdf` (30 Oct 2026), team guide `Warehouse Rush · Guía de arranque con Claude Code` (4 Nov 2026, **only pages 1-4 of 10 were provided**), `Warehouse Rush · Guía R2`. Guides for R1, R3 and R4 were not seen; their content below comes only from the team guide's role table.

**The user is R2 · Entrenamiento y experimentos.** Teammates (remote branches): angie, lis, miguel, naomi. Which person has which role is not recorded in the PDFs; ask if it matters.

## What we deliver
A Vercel web app showing how a PPO agent evolves in Warehouse Rush. The teacher must be able to browse experiments, load historical models and run evaluations with each model's compatible environment. Deliverable = environment + agent + visualization + experiments + models + pipeline + deployment, all versioned so any result can be explained, reproduced and rolled back. **Failed/rejected attempts are kept**; traceability is graded even when a candidate does not improve.

Rubric: versioning, traceability, historical recovery **30%** · experimental design, comparison, analysis **25%** · pipeline, deployment, monitoring, rollback **20%** · env/agent contract **10%** · individual defense **15%** (everyone must explain contract, versioning, deploy/reproduce, not only their part). Using code assistants does not replace that explanation: record decisions.

## The 4 roles (one owner per folder so Git does not conflict)
| Role | Owns | Key outputs | Rubric |
|---|---|---|---|
| R1 Env and rules | `envs/`, `tests/`, `docs/ambiente-v0.1.md` | Gymnasium env, `envs/CONTRATO.md`, rule tests, N1-N3, closed-aisle incident, rule-based controller `envs/heuristica.py` | contract 10% |
| **R2 Training and experiments (user)** | `configs/experiments/`, `configs/suites/`, `configs/criterios.yaml`, `pipelines/{train,evaluate,baselines,callbacks,compare}.py`, `docs/experimentos.md` | random + rule references, PPO baseline per level, fixed eval suites, 4+ hypothesis configs, 2 finalists x 3 seeds, N3 incident measurement | experimental design 25% |
| R3 Versioner, pipeline, API | `pipelines/{flow,registry,tracking}.py`, `manifests/`, `api/`, `dvc.yaml` | persistent MLflow, DVC, SHA-256 manifests, model catalog, Prefect flow, FastAPI, rollback test | versioning 30% + pipeline 20% |
| R4 Web and deploy | `web/` | Vite+TS+Three.js scene, catalog, comparison, modes (manual/random/reference/evaluation/training), Vercel URL | pipeline/deploy 20% (shared) |

Open team decisions (agree with the teacher): where persistent MLflow lives, where the HTTPS API is hosted, Prefect vs Airflow.

Extra brief details (Warehouse Rush scenario text, levels, web build order, architecture, final package, milestones, setup steps): bottom of [references/requirements.md](references/requirements.md).

Details: [references/roles.md](references/roles.md) (per-role asks and cross-role requirements), [references/requirements.md](references/requirements.md) (course requirements and acceptance checks).

## Versioning (the highest-weight area)
Everything about how we version lives in [references/versioning.md](references/versioning.md): branches, commits, tags, DVC, MLflow, run names, manifest schema, model package, `.gitignore`, rollback. Read it before touching any artifact. R3 owns it; R2 consumes it.

## R2 playbook
Experiment design, configs, suites, selection criteria, hypotheses C0-C4, finalists, MLflow logging, prompts per phase, checklist: [references/r2-experiments.md](references/r2-experiments.md).

## Environment spec
Original design sheet for the Warehouse Rush env (world, obs/action, reward, reward-hacking challenge): [references/env-spec.md](references/env-spec.md). **That sheet describes the original idea, not the current env.** The current contract (v7), the v1-v7 timeline, tags and commits: [references/env-versions.md](references/env-versions.md); in the repo `envs/CONTRATO.md` is the frozen source of truth.

## Experiment log and workflow
- What we ran, results, diagnoses, lessons and open items: [references/experiment-log.md](references/experiment-log.md). **Read it before proposing a new experiment** (several obvious ideas were already tried and failed).
- How to train, evaluate, diagnose, document, tag and commit, plus pitfalls: [references/workflow.md](references/workflow.md). Helper scripts: `scripts/eval_run.py <run>` (official deterministic eval), `scripts/trace_policy.py <run>` (key-state diagnosis) and `scripts/eval_stochastic.py <run> [--seed-start 20000]` (exploratory sampled-action eval). Behaviour cloning: `python -m pipelines.bc --config ...` (see workflow.md).

## Non-negotiable rules
- Python simulation is the authority; Three.js only renders state.
- Obs/action order, units and ranges frozen in `envs/CONTRATO.md`; any change to them **or to the reward function** bumps the env version (currently `warehouse-v7`) with an annotated tag `env/warehouse-vN`, a new `docs/ambiente-v0.N.md` and a row in `docs/decisiones.md`.
- `terminated` = mission success/failure; `truncated` = step limit. Log both.
- Reward milestones paid once per order; pick/drop loop must not profit.
- Never overwrite a registered model: create a new version.
- Never commit `.venv/`, `node_modules/`, `.env`, local `mlruns/`, `mlflow.db`, big weights, the reserved `test-final` suite. `models/*` is git-ignored, so trained weights are local only until the team agrees a DVC remote.
- Hypothesis, criterion and scripted baselines are written in `docs/experimentos.md` **before** training; criteria are never changed after seeing results; every run (including failures) gets a manifest, an MLflow `estado` and a results section.
- Return is not success rate; never compare returns across different rewards/worlds.
- Python 3.12, PyTorch CPU, frozen `requirements.txt`; Node LTS with `package-lock.json` (`npm ci`).

## Current state (2026-11-14, branch `dev/lis`, many commits ahead of `origin/dev/lis`, nothing pushed; verify with `git log` and `git tag`)
**Environment:** `ENV_VERSION="warehouse-v10"` (ficha 0.10.0). Only the **makeup mode** is trained: `Box(27)` observation (own xy, target xy, facing an interactable, tray elevation, target elevation), `Discrete(8)` actions (AVANZAR, GIRAR_I, GIRAR_D, FRENAR, CARGAR, DESCARGAR, SUBIR, BAJAR; one tray position per SUBIR/BAJAR), 25x19 warehouse with 6 racks x 3 shelf levels, inventory/orders, conveyor + box, battery 180, 400 steps. Reward coefficients are a per-run parameter (YAML `recompensa:`); v5 added `manhattan_progress` and `height_mismatch`; v6 added `lower_bonus` (rejected, **removed** in v7); v7 added `carry_milestone` (once per delivery leg at half the distance to dispatch, default 0); v8 added `face_bonus` (once per target station per episode when facing it from an interaction cell, default 0); v9 added `potential` (one potential-based shaping weight over staged Phi, default 0) and a training-only stagnation stop (`parada_estancamiento`); v10 added `potential_nav` (navigation weight inside phi, 0 removes it). Maps: `layout_v0.4.json` (walled) and `layout_v0.5.json` (open). Levels: `m1` (walled), `m1o` (open), both with 3 random distinct SKUs per episode. Full detail: [references/env-versions.md](references/env-versions.md). The v1 env (two floor stations, `Box(22)`, `Discrete(5)`) and its models are history and incompatible.

**History in one paragraph:** dev/angie (inventory, makeup missions, elevator, wide map, conveyor) was merged into the plan's folder layout (`envs/`, `pipelines/`, `api/`), the user then redefined the observation and actions (v2), made the reward a per-run parameter (v3), added a Manhattan distance penalty and an open map (v4), a Manhattan-difference term and a tray-height penalty (v5), a lower-the-tray bonus and `time` -0.2 test (v6, rejected), and a delivery-leg milestone (v7). Tags `env/warehouse-v2` (`b878762`), `-v3` (`30c34fb`), `-v4` (`1b82ca9`), `-v5` (`2b80031`), `-v6` (`cc968ff`), `-v7` (`c152c42`). Behaviour cloning (`pipelines/bc.py`, no env change) was added after v7.

**Results, short (everything on `suite-m1o-v1`, deterministic eval, 50 episodes; heuristic 100%, ~71 steps):**
- Every run on v1-v4 and the first v5 sweep scored 0% (idling, avoiding the rack, spamming invalid actions, or stalling after loading). First model that completes the mission: `m1o-e4l-seed0` (e4 reward, open map, **606 208 steps**): 92%; seeds 1 and 2 got 0%, control 0%; criterion met on the 3-seed mean (30.7%) but carried by one seed, so nothing is `recomendado`.
- `f1-f3` (v6: `time` -0.2 and/or `lower_bonus` 1.0): 0 / 0 / 0%, 44% (time only, seed 0), 0%: rejected. The bonus made the agent lower the tray but it then spun instead of driving to dispatch; `time` -0.2 did not shorten successes (73.6 vs 71.8 steps) and cut success.
- `g1` (v7 `carry_milestone` 5.0): 94 / 0 / 0%, mean 31.3% vs 30.7%: rejected (+0.7 pp). seed 1 is bit-identical to e4l-seed1 (never loads). Sampled-action diagnostic (post hoc): g1-seed2 94% vs e4l-seed2 about 1%, so the milestone worked there but argmax evaluation hid it.
- `h0` (behaviour cloning of the heuristic only): **100 / 100 / 100%**, 71 steps, 0 collisions: the 27-dim observation suffices; the bottleneck of e4l/g1 was discovering the task. `h1` (PPO 600k from h0 with the e4l reward): 88 / 92 / 100%, mean 93.3% (+62.7 pp) but collisions 2.25/ep (seed 0: 6.74) vs limit +0.1, so **rejected by the pre-registered two-part criterion**. PPO fine-tuning degrades the imitator from the first checkpoint. h0 copies a privileged controller: a reference, not RL evidence. No run is `recomendado`.
Full tables, diagnoses and lessons: [references/experiment-log.md](references/experiment-log.md).

**Tests:** 173 collected at HEAD (167 passed at `env/warehouse-v7`, `docs/resultados/pytest-warehouse-v7.xml`; 6 added later in `tests/test_reward_config.py` (more-seeds configs) and `tests/test_bc.py` (5)). Manifests: 37 run manifests + `schema.json` in `manifests/` (run manifests validate against `manifests/schema.json`, which accepts levels `n1, n2, n3, m1, m1o`).

**Cancelled / not done:** seeds 3-7 of `e4l` and `g1` were configured and pre-registered but **stopped at about 50%** (g1 3-7, status `interrumpido`, no results) or never launched (e4l 3-7) when the user switched to behaviour cloning; configs remain in `configs/experiments/`. Other open items are listed in [references/experiment-log.md](references/experiment-log.md) (section "Open items"). Plan gaps unchanged: finalists x 3 seeds and `test-final`, `compare.py`, `callbacks.py`, suite-driven `evaluate.py`, Prefect flow, FastAPI, DVC/MLflow remotes (weights local only, including `models/m1o-e4l-seed0/model.zip` and the h0/h1 models), web viewer not rebuilt for v2-v7, push to origin and PR to `main`, tell R3 about the schema levels `m1`/`m1o` and R1 about the env versions.

## Working conventions with this user (learned in sessions)
- All work on `dev/lis`; Spanish commits and Spanish project docs; this skill is in English. Do not push unless asked. Commit **before** launching training; tag env versions.
- The user decides the experiments and gives exact reward values; implement exactly what is asked, flag assumptions (for example "open map = interior wall removed, racks kept", "3 SUBIR for shelf 3 because the stowed position is not a shelf", "bonus only with target DELIVERY") and correct course openly when a rule applies (a reward-function change bumps the version). When the user asks for two changes at once (v6: time + bonus), run the combination and one-change ablations so the effect can be attributed.
- For environment tests the user prioritizes **the environment working over the agent working**: test rules, contract and reward terms, not model quality.
- The user redirects quickly: it stopped the more-seeds runs to try behaviour cloning, and asked "how long left?" repeatedly. For time estimates **measure** (elapsed seconds of the process and `time/total_timesteps` in `docs/resultados/training/<run>/progress.csv`), never guess; for "is it done?" check the real state before answering. Mention that concurrent tests/scripts slow training (5 parallel runs ran at about 290 steps/s, not 540).
- When a pre-registered criterion fails on one condition, report the other numbers honestly but keep the verdict (h1: +62.7 pp but collisions failed; g1 sampled eval much better than deterministic). Exploratory diagnostics decided after seeing results never change the official status; say that explicitly and propose a new pre-registered criterion if the user wants it.
- Present results as tables with the measured facts first, then the decision by the pre-set criterion, then diagnosis, then limitations; separate measured facts from hypotheses; never claim learning from a single seed; say plainly when something failed or was not run.
- Explain in plain language when asked (the user asked for step-by-step descriptions of what the agent observes and does, and of the reward).
- When writing to the skill for the user: update SKILL.md (state), env-versions, experiment-log, workflow, and also the project memory snapshot.
