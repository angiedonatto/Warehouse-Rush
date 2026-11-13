---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract, reward-hacking checks. The user is R2 (Entrenamiento y experimentos).
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
Original design sheet for the Warehouse Rush env (world, obs/action, reward, reward-hacking challenge): [references/env-spec.md](references/env-spec.md).

## Non-negotiable rules
- Python simulation is the authority; Three.js only renders state.
- Obs/action order, units and ranges frozen in `envs/CONTRATO.md`; any change bumps env version (`warehouse-v1` -> `warehouse-v2`) and starts a new model family.
- `terminated` = mission success/failure; `truncated` = step limit. Log both.
- Reward milestones paid once per order; pick/drop loop must not profit.
- Never overwrite a registered model: create a new version.
- Never commit `.venv/`, `node_modules/`, `.env`, local `mlruns/`, `mlflow.db`, big weights, the reserved `test-final` suite.
- Return is not success rate; never compare returns across different rewards/worlds.
- Python 3.12, PyTorch CPU, frozen `requirements.txt`; Node LTS with `package-lock.json` (`npm ci`).

## Current repo state (2026-11-06, after merging dev/angie)
Angie's work (env, PPO, baselines, Three.js viewer, Vercel deploy, experiment 001) was merged and **relocated into the plan's structure**: `envs/` (env, layout, rewards), `pipelines/` (train, evaluate, baselines, cli, tracking), `api/` (`index.py` entry, `_cloud.py`, `_viewer.py`), `docs/resultados/`, `manifests/experiment-001.json`, `models/experiment-001/`. The Q-learning prototype was removed. `ENV_VERSION="warehouse-v1"`. Action space is `Discrete(5)` and obs `Box(22,)` (not the guide's `MultiDiscrete([3,3,2])`); N2 is 2 orders (guide says 3). `python -m pipelines.train --config configs/experiments/<x>.yaml` trains from YAML and logs to MLflow. Model, hyperparameters and retraining: `docs/modelo-actual.md`. Missing: compare.py, callbacks.py, suite-driven evaluate.py, full tracking/registry, Prefect flow, FastAPI, DVC/MLflow remotes. Working branch: `dev/lis` (the user's branch; all changes go there).


## Update 2026-11-13: warehouse-v2 (makeup mode only)
dev/angie (inventory, makeup missions, elevator, wide map v0.4, conveyor/box) was merged into dev/lis with its modules relocated to `envs/` (handling, inventory, missions). **`ENV_VERSION="warehouse-v2"`**: obs `Box(27)` (own xy, target xy, facing interactable, tray elevation, target elevation), actions `Discrete(8)` (AVANZAR, GIRAR_I, GIRAR_D, FRENAR, CARGAR, DESCARGAR, SUBIR, BAJAR; one tray position per SUBIR/BAJAR: 0.55/0.99/1.79/2.60 m). Contract: `envs/CONTRATO.md`; sheet: `docs/ambiente-v0.2.md`. Only makeup mode is trained. Level `m1` = 3 random distinct SKUs of 1 unit per episode, stock restocked on reset (`envs.make_env(orders=3)`). First v2 run: `m1-c0-seed0` (config `configs/experiments/m1_c0_makeup3.yaml`, C0 hyperparameters unchanged). v1 configs (`c0`-`c6`) and models are history and incompatible. Suites for m1: `dev-m1-v1`, `suite-m1-v1`.

**Update (same day): warehouse-v3** = v2 + reward coefficients as a per-run parameter (`recompensa:` block in the YAML; defaults = v1/v2). Tag `env/warehouse-v3`. Sweep of `invalid_interaction` (-2 control c0b, -1 r1, -0.2 r2, -0.05 r3): all 0% success, r1-r3 rejected. Next candidates: lower collision penalty, once-per-line sub-step bonuses, or behaviour cloning from the heuristic.
Second sweep (invalid -0.2 fixed; collision -2/-1/-0.5/-0.1 = r4-r7, control r2): all 0%, rejected. Lowering penalties further is a dead end (wall-bumping trap at -0.5/-0.1). Next: once-per-line sub-step bonuses or behaviour cloning.
