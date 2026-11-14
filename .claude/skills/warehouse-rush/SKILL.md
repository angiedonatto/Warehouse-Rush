---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract and its versions warehouse-v1 to v5, the full experiment log (what was tried, what worked, what failed and why), how to run/evaluate/diagnose/document an experiment, reward-hacking checks. The user is R2 (Entrenamiento y experimentos) and has also been changing the environment on the team's instruction.
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
Original design sheet for the Warehouse Rush env (world, obs/action, reward, reward-hacking challenge): [references/env-spec.md](references/env-spec.md). **That sheet describes the original idea, not the current env.** The current contract (v5), the v1-v5 timeline, tags and commits: [references/env-versions.md](references/env-versions.md); in the repo `envs/CONTRATO.md` is the frozen source of truth.

## Experiment log and workflow
- What we ran, results, diagnoses, lessons and open items: [references/experiment-log.md](references/experiment-log.md). **Read it before proposing a new experiment** (several obvious ideas were already tried and failed).
- How to train, evaluate, diagnose, document, tag and commit, plus pitfalls: [references/workflow.md](references/workflow.md). Helper scripts: `scripts/eval_run.py <run>` and `scripts/trace_policy.py <run>`.

## Non-negotiable rules
- Python simulation is the authority; Three.js only renders state.
- Obs/action order, units and ranges frozen in `envs/CONTRATO.md`; any change to them **or to the reward function** bumps the env version (currently `warehouse-v6`) with an annotated tag `env/warehouse-vN`, a new `docs/ambiente-v0.N.md` and a row in `docs/decisiones.md`.
- `terminated` = mission success/failure; `truncated` = step limit. Log both.
- Reward milestones paid once per order; pick/drop loop must not profit.
- Never overwrite a registered model: create a new version.
- Never commit `.venv/`, `node_modules/`, `.env`, local `mlruns/`, `mlflow.db`, big weights, the reserved `test-final` suite. `models/*` is git-ignored, so trained weights are local only until the team agrees a DVC remote.
- Hypothesis, criterion and scripted baselines are written in `docs/experimentos.md` **before** training; criteria are never changed after seeing results; every run (including failures) gets a manifest, an MLflow `estado` and a results section.
- Return is not success rate; never compare returns across different rewards/worlds.
- Python 3.12, PyTorch CPU, frozen `requirements.txt`; Node LTS with `package-lock.json` (`npm ci`).

## Current state (2026-11-13, branch `dev/lis`, 33 commits ahead of `origin/dev/lis` before this skill update, nothing pushed; verify with `git log`)
**Environment:** `ENV_VERSION="warehouse-v6"` (ficha 0.6.0). Only the **makeup mode** is trained: `Box(27)` observation (own xy, target xy, facing an interactable, tray elevation, target elevation), `Discrete(8)` actions (AVANZAR, GIRAR_I, GIRAR_D, FRENAR, CARGAR, DESCARGAR, SUBIR, BAJAR; one tray position per SUBIR/BAJAR), 25x19 warehouse with 6 racks x 3 shelf levels, inventory/orders, conveyor + box, battery 180, 400 steps. Reward coefficients are a per-run parameter (YAML `recompensa:`); v5 added `manhattan_progress` and `height_mismatch`; v6 added `lower_bonus` (once per leg and tray level). Maps: `layout_v0.4.json` (walled) and `layout_v0.5.json` (open). Levels: `m1` (walled), `m1o` (open), both with 3 random distinct SKUs per episode. Full detail: [references/env-versions.md](references/env-versions.md). The v1 env (two floor stations, `Box(22)`, `Discrete(5)`) and its models are history and incompatible.

**History in one paragraph:** dev/angie (inventory, makeup missions, elevator, wide map, conveyor) was merged into the plan's folder layout (`envs/`, `pipelines/`, `api/`), the user then redefined the observation and actions (v2), made the reward a per-run parameter (v3), added a Manhattan distance penalty and an open map (v4), and added a Manhattan-difference term and a tray-height penalty (v5). Tags `env/warehouse-v2` (`b878762`), `-v3` (`30c34fb`), `-v4` (`1b82ca9`), `-v5` (`2b80031`).

**Results, short:** every run scored **0%** success except one (the policy collapses to idling, avoids the rack, spams invalid actions, or stalls after loading). The first model that completes the mission is `m1o-e4l-seed0` (e4 reward = collision -1, invalid -0.2, `manhattan_progress` 0.3, `height_mismatch` -0.02, open map, **606 208 steps**): **92% success** on `suite-m1o-v1` (heuristic 100%). The other two seeds (1, 2) scored 0%, and the same-budget control scored 0%; the pre-registered criterion is met on the 3-seed mean (30.7% +- 43.4 pp) but carried by one seed, so **no run is `recomendado`**. The curve of seed 0 shows the first success at 340k steps, so 200k is not enough. Full tables, diagnoses and lessons: [references/experiment-log.md](references/experiment-log.md).

**Tests:** 166 pass at `env/warehouse-v6` (`docs/resultados/pytest-warehouse-v6.xml`, plus 1 test added later for the f-configs); `tests/test_reward_config.py` (34) passes at HEAD. Manifests: 28 files in `manifests/` (all validate against `manifests/schema.json`, which accepts levels `n1, n2, n3, m1, m1o`).

**Not done / open (none started):** more seeds of `e4l`; e4 reward on the walled map; once-per-line bonuses (would be `warehouse-v6`); behaviour cloning; finalists x 3 seeds and `test-final`; `compare.py`, `callbacks.py`, suite-driven `evaluate.py`; Prefect flow, FastAPI; DVC and MLflow remotes (weights are local only, including the 188 KB `models/m1o-e4l-seed0/model.zip`); web viewer not rebuilt or tested against v2-v5; push to origin and PR to `main`; tell R3 about the schema levels `m1`/`m1o` and R1 about the env versions.

## Working conventions with this user (learned in sessions)
- All work on `dev/lis`; Spanish commits and Spanish project docs; this skill is in English. Do not push unless asked. Commit **before** launching training; tag env versions.
- The user decides the experiments and gives exact reward values; implement exactly what is asked, flag assumptions (for example "open map = interior wall removed, racks kept", "3 SUBIR for shelf 3 because the stowed position is not a shelf") and correct course openly when a rule applies (a reward-function change bumps the version).
- For environment tests the user prioritizes **the environment working over the agent working**: test rules, contract and reward terms, not model quality.
- Present results as tables with the measured facts first, then the decision by the pre-set criterion, then diagnosis, then limitations; separate measured facts from hypotheses; never claim learning from a single seed; say plainly when something failed or was not run (for example the walled-map run was skipped because its condition was not met).
- Explain in plain language when asked (the user asked for step-by-step descriptions of what the agent observes and does, and of the reward).
