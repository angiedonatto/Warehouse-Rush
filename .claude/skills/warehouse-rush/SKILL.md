---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract and its versions warehouse-v1 to v10, the walled-map campaign of 2026-11-14/15, behaviour cloning from the heuristic (pipelines/bc.py), the full experiment log (what was tried, what worked, what failed and why), how to run/evaluate/diagnose/document an experiment, reward-hacking checks, MLflow on DagsHub (migration, registry), the web/API (served models, model catalog, evaluate route, Naomi's 27-product catalog), and the deliverables status vs the brief (as of 2026-11-18 only R3 is missing: Prefect flow, rollback test, Vercel deploy). The user is R2 (Entrenamiento y experimentos) and has also done the environment and the R4 web integration on the team's instruction.
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

Naomi did the R4 visual work (27-product Trendy catalog, GLB assets, pink UI) on `dev/naomi`; the user (Lis) merged it into the plan structure and finished R4 (served models, model catalog, evaluate route, modes, deep links) on 2026-11-18. **Status and the R3 handover: [references/status.md](references/status.md).**

Open team decisions (agree with the teacher): Prefect vs Airflow (Prefect 3.8.8 is pinned; R3 should decide and log it). API = Vercel Python function `api/index.py` (60 s limit). **Decided 2026-11-18: persistent MLflow = DagsHub** (`https://dagshub.com/mamezquita/Warehouse-Rush.mlflow`, public read; see versioning.md section 6).

Extra brief details (Warehouse Rush scenario text, levels, web build order, architecture, final package, milestones, setup steps): bottom of [references/requirements.md](references/requirements.md).

Details: [references/roles.md](references/roles.md) (per-role asks and cross-role requirements), [references/requirements.md](references/requirements.md) (course requirements and acceptance checks).

## Versioning (the highest-weight area)
Everything about how we version lives in [references/versioning.md](references/versioning.md): branches, commits, tags, DVC, MLflow, run names, manifest schema, model package, `.gitignore`, rollback. Read it before touching any artifact. R3 owns it; R2 consumes it.

## R2 playbook
Experiment design, configs, suites, selection criteria, hypotheses C0-C4, finalists, MLflow logging, prompts per phase, checklist: [references/r2-experiments.md](references/r2-experiments.md).

## Environment spec
Original design sheet for the Warehouse Rush env (world, obs/action, reward, reward-hacking challenge): [references/env-spec.md](references/env-spec.md). **That sheet describes the original idea, not the current env.** The v1-v10 timeline, tags, the current contract summary and the product-catalog parameter: [references/env-versions.md](references/env-versions.md); in the repo `envs/CONTRATO.md` is the frozen source of truth.

## Experiment log and workflow
- What we ran, results, diagnoses, lessons and open items: [references/experiment-log.md](references/experiment-log.md). **Read it before proposing a new experiment** (several obvious ideas were already tried and failed).
- How to train, evaluate, diagnose, document, tag and commit, plus pitfalls: [references/workflow.md](references/workflow.md). Helper scripts: `scripts/eval_run.py <run>` (official deterministic eval), `scripts/trace_policy.py <run>` (key-state diagnosis) and `scripts/eval_stochastic.py <run> [--seed-start 20000]` (exploratory sampled-action eval). Behaviour cloning: `python -m pipelines.bc --config ...` (see workflow.md).

## Non-negotiable rules
- Python simulation is the authority; Three.js only renders state.
- Obs/action order, units and ranges frozen in `envs/CONTRATO.md`; any change to them **or to the reward function** bumps the env version (currently `warehouse-v10`) with an annotated tag `env/warehouse-vN`, a new `docs/ambiente-v0.N.md` and a row in `docs/decisiones.md`.
- `terminated` = mission success/failure; `truncated` = step limit. Log both.
- Reward milestones paid once per order; pick/drop loop must not profit.
- Never overwrite a registered model: create a new version.
- Never commit `.venv/`, `node_modules/`, `.env`, local `mlruns/`, `mlflow.db`, big weights, the reserved `test-final` suite. `models/*` is git-ignored: weights go to DVC (remote `r2`, Cloudflare R2). Exceptions committed on purpose: `models/experiment-001/` (history) and `models/servidos/` (the recommended weights the Vercel API serves, ~184 KB each; Vercel cannot reach DVC).
- Secrets never in Git or chat output: R2 keys only in `.dvc/config.local`, DagsHub token only in `.env` (both ignored). Scan staged diffs for them before committing.
- `main` only through a PR (the user explicitly asked to merge PR #2 without team review on 2026-11-18; do not assume that again).
- Hypothesis, criterion and scripted baselines are written in `docs/experimentos.md` **before** training; criteria are never changed after seeing results; every run (including failures) gets a manifest, an MLflow `estado` and a results section.
- Return is not success rate; never compare returns across different rewards/worlds.
- Python 3.12, PyTorch CPU, frozen `requirements.txt`; Node LTS with `package-lock.json` (`npm ci`).

## Current state (2026-11-18; `main` == `dev/lis` after PR #2, merge `da14120`; verify with `git log origin/main`)
**Deliverables:** everything except R3 is done; see [references/status.md](references/status.md) (checklist vs the brief plus a concrete R3 handover). Missing: Prefect flow, rollback doc+test, Vercel deploy of the current version (the live site still serves the old `experiment-001` build), then tag `v1.0`, report and presentation.

**Environment:** `warehouse-v10` (ficha 0.10.0, tags `env/warehouse-v2`..`v10`). Makeup mode only: `Box(27)` obs, `Discrete(8)` actions, 25x19 warehouse, 6 racks x 3 levels. Maps `layout_v0.4.json` (walled; course scenario) and `layout_v0.5.json` (open). Levels: N1 = `m1o` (open), N2 = `m1` (walled), N3 = `m1b` (gap (6,14) closed). Product catalog is a scenario parameter: `make_env` pins `legacy-18` (what every run was trained/evaluated on); the web uses Naomi's `trendy-27-v1` (diagnostic: recommended models 100% with it). Details: env-versions.md.

**Models:** `m1b-i1-seed1-best` = production (`recomendado` for N3; test-final-m1b-v1 100/100 open + 100/100 closed). `m1-c3-seed0` = `recomendado` for N2 and the rollback (test-final-m1-v1 100/100). Both reserved test-final suites are used up: never run another model on them without a new pre-registration. Experiment history (v1-v10, walled-map campaign, potential shaping failure, entropy, best-checkpoint rule, incident N3 and intervention): [references/experiment-log.md](references/experiment-log.md).

**Versioning and tracking:** weights of 90 runs in DVC on Cloudflare R2; 82 manifests (with `mlflow_run_id` = DagsHub id, `mlflow_run_id_local` = old id); MLflow on DagsHub (94 runs migrated with `pipelines/migrar_mlflow.py`, map `docs/resultados/mlflow-migracion.json`, old sqlite as DVC snapshot `mlflow.db.dvc`/`mlruns.dvc`); Model Registry `warehouse-m1` v1 and `warehouse-m1b` v1 with alias `recomendado` (`pipelines/registrar_modelos.py`). Details: versioning.md.

**Web/API (R4, 2026-11-18):** the API serves the recommended models (`pipelines/servir.py` -> `models/servidos/` + `configs/modelos_servidos.json`, sha256 verified at load; in cloud mode an episode is step-identical to the direct evaluation); dialog «Modelos y experimentos» (82 models from `pipelines/catalogo.py` -> `web/public/modelos/catalogo.json`) with Cargar / Evaluar 10 episodios / Comparar; `POST /api/evaluate` (stateless, per-episode results + monitoring: inference latency, errors, served sha256); mode badge; deep links `?modelo=<id>&cerrado=1&semilla=N` and `?catalogo=<id>`. The degradation is demonstrable live: `m1-c3-seed0` with the gap closed fails (about 85 collisions/ep), `m1b-i1-seed1-best` solves it.

**Tests:** 280 Python tests pass (`-n 6 --dist loadfile`, about 50 s); 12 Playwright tests pass against the local viewer (`python -m pipelines.cli view --no-open`, port 8080) and the cloud-mode tests pass against `api._cloud.preview(port)`. How to run Chromium in this WSL without sudo: workflow.md ("Browser tests").

## Working conventions with this user (learned in sessions)
- All work on `dev/lis`; Spanish commits and Spanish project docs; this skill is in English. Do not push unless asked. Commit **before** launching training; tag env versions.
- The user decides the experiments and gives exact reward values; implement exactly what is asked, flag assumptions (for example "open map = interior wall removed, racks kept", "3 SUBIR for shelf 3 because the stowed position is not a shelf", "bonus only with target DELIVERY") and correct course openly when a rule applies (a reward-function change bumps the version). When the user asks for two changes at once (v6: time + bonus), run the combination and one-change ablations so the effect can be attributed.
- For environment tests the user prioritizes **the environment working over the agent working**: test rules, contract and reward terms, not model quality.
- The user redirects quickly: it stopped the more-seeds runs to try behaviour cloning, and asked "how long left?" repeatedly. For time estimates **measure** (elapsed seconds of the process and `time/total_timesteps` in `docs/resultados/training/<run>/progress.csv`), never guess; for "is it done?" check the real state before answering. Mention that concurrent tests/scripts slow training (5 parallel runs ran at about 290 steps/s, not 540).
- When a pre-registered criterion fails on one condition, report the other numbers honestly but keep the verdict (h1: +62.7 pp but collisions failed; g1 sampled eval much better than deterministic). Exploratory diagnostics decided after seeing results never change the official status; say that explicitly and propose a new pre-registered criterion if the user wants it.
- Present results as tables with the measured facts first, then the decision by the pre-set criterion, then diagnosis, then limitations; separate measured facts from hypotheses; never claim learning from a single seed; say plainly when something failed or was not run.
- Explain in plain language when asked (the user asked for step-by-step descriptions of what the agent observes and does, and of the reward).
- When writing to the skill for the user: update SKILL.md (state), env-versions, experiment-log, workflow, status, and also the project memory snapshot.
- **Answer the user in Spanish** (asked 2026-11-18). The skill stays in English.
- **Build on teammates' work, never redo it from scratch** (user, 2026-11-18): merge their branch keeping authorship, adapt only paths and what conflicts, reuse their UI components/classes, and adapt their tests only where the environment really changed (document why).
- Before integrating a teammate's change that touches the environment (e.g. a new product catalog), measure its effect on the recommended models on the fixed suites and keep training/evaluation reproducible (parameterize instead of silently changing defaults).
- The user asks broad questions ("what is missing?", "does it comply with the brief?"): check the repo and the live services against requirements.md, not memory, and answer with done / missing / owner.
