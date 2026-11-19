---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract and its versions warehouse-v1 to v10, the walled-map campaign of 2026-11-14/15, behaviour cloning from the heuristic (pipelines/bc.py), the full experiment log (what was tried, what worked, what failed and why), how to run/evaluate/diagnose/document an experiment, reward-hacking checks, MLflow on DagsHub (migration, registry), the web/API (Render FastAPI as the single server, X-Sesion sessions, official async evaluations, model catalog, Naomi's 27-product catalog), Vercel deploys and browser tests, and the deliverables status vs the brief (v1.0 released 2026-11-19; remaining: short report, presentation, teacher sign-off on infra). The user is R2 (Entrenamiento y experimentos) and has also done the environment and the R4 web integration on the team's instruction.
---

# Warehouse Rush: MLOps final project

Sources (PDFs in Windows Downloads, read 2026-11-06): course brief `Enunciado-proyecto-final-MLOps.pdf` (30 Oct 2026), team guide `Warehouse Rush · Guía de arranque con Claude Code` (4 Nov 2026, **only pages 1-4 of 10 were provided**), `Warehouse Rush · Guía R2`. Guides for R1, R3 and R4 were not seen; their content below comes only from the team guide's role table.

**The user is R2 · Entrenamiento y experimentos.** Team (confirmed by the user 2026-11-19): **Angie Donato = R1** (environment and rules), **Lis Sánchez = R2** (the user), **Miguel Amézquita = R3** (versioning, pipeline, API), **Naomi Mosquera = R4** (web and deploy). GitHub: `angiedonatto` (repo owner, admin), `Lis-Sanchez-DS`, `mamezquita`, `naomiv2910-cell` (all write; `main` has no branch protection).

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

Team decisions (all logged in `docs/decisiones.md`; still to be confirmed with the teacher): **orchestrator = Prefect** (`pipelines/flow.py`); **MLflow = DagsHub** (`https://dagshub.com/mamezquita/Warehouse-Rush.mlflow`, public read); **DVC remote = Cloudflare R2**; **API = FastAPI on Render** (`https://warehouse-rush-api.onrender.com`, Hugging Face Spaces needed PRO), the **single** model/episode server since 2026-11-18; Vercel serves only the web since v1.0 (`api/index.py` removed).

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
- Never commit `.venv/`, `node_modules/`, `.env`, local `mlruns/`, `mlflow.db`, big weights, the reserved `test-final` suite. `models/*` is git-ignored: weights go to DVC (remote `r2`, Cloudflare R2). Exceptions committed on purpose: `models/experiment-001/` (history), `models/numpy/` (NumPy exports of the 20 API-executable PPO policies, what Render serves) and `models/servidos/` (torch weights the retired Vercel API served; dead code, R3 to remove).
- Secrets never in Git or chat output: R2 keys only in `.dvc/config.local`, DagsHub token only in `.env` (both ignored). Scan staged diffs for them before committing.
- `main` only through a PR; never push commits directly to `main`. Work on a task branch (`dev/lis-*`) and push only that branch. Merges so far: PR #2/#3 by the user's request, #1/#4/#5/#6/#7 by Angie, #8/#9 by Claude on the user's explicit request during the final stretch (2026-11-19). Ask again before merging in a new session.
- Hypothesis, criterion and scripted baselines are written in `docs/experimentos.md` **before** training; criteria are never changed after seeing results; every run (including failures) gets a manifest, an MLflow `estado` and a results section.
- Return is not success rate; never compare returns across different rewards/worlds.
- Python 3.12, PyTorch CPU, frozen `requirements.txt`; Node LTS with `package-lock.json` (`npm ci`).

## Current state (2026-11-19; **v1.0 released**, `main` = `211acdf`; verify with `git log origin/main`)
**Release:** tag `v1.0` on `f72f0a2` (the deployed commit), GitHub release https://github.com/angiedonatto/Warehouse-Rush/releases/tag/v1.0 (notes: URLs, Render commit, verification, team). **Deliverables:** [references/status.md](references/status.md). Remaining: short report, final presentation, confirm infra with the teacher, R3 dead-code cleanup.

**Architecture (one server):** web on Vercel (https://warehouse-rush-psi.vercel.app, project `warehouse-rush`, team `lis-team2`, static `web/dist` only; `/api/*` there returns 404) -> API FastAPI on Render (https://warehouse-rush-api.onrender.com, image `ghcr.io/mamezquita/warehouse-rush-api:<sha>`, commit `8b49d63` at v1.0, production model `m1b-i1-seed1-best@46984e97b032`, inference NumPy from `models/numpy/`, no torch). Contract for the web: `docs/api-contrato.md` (sec. 9 = `/api/*` layer with the old viewer routes, session in header `X-Sesion`). Render Free sleeps after 15 min (first request ~18-20 s) and has 0.1 CPU (official 50-episode eval ~25 s; failing model > 1 min).

**Environment:** `warehouse-v10` (ficha 0.10.0, tags `env/warehouse-v2`..`v10`). Makeup mode only: `Box(27)` obs, `Discrete(8)` actions, 25x19 warehouse, 6 racks x 3 levels. Maps `layout_v0.4.json` (walled; course scenario) and `layout_v0.5.json` (open). Levels: N1 = `m1o` (open), N2 = `m1` (walled), N3 = `m1b` (gap (6,14) closed). Product catalog is a scenario parameter: `make_env` pins `legacy-18` (training, official evaluations, `certificado: true`); web episodes use Naomi's `trendy-27-v1` (API `/layout` and episodes agree since Miguel's fix `4c78506`). Details: env-versions.md.

**Models:** `m1b-i1-seed1-best` = production (`recomendado` for N3; test-final-m1b-v1 100/100 open + 100/100 closed). `m1-c3-seed0` = `recomendado` for N2 and the rollback (`anterior` in `manifests/aliases.json`; test-final-m1-v1 100/100). Both reserved test-final suites are used up. 20 models are executable by the API (`evaluable_con_api` in `manifests/catalog.json`). History: [references/experiment-log.md](references/experiment-log.md).

**Versioning and tracking:** weights of 90 runs in DVC on R2; 82 manifests (`mlflow_run_id` = DagsHub id, `mlflow_run_id_local` = old id; accepted by the team, `pipelines/flow.py::_run_origen` finds runs either way); MLflow on DagsHub (94 runs migrated); Model Registry `warehouse-m1`/`warehouse-m1b` v1 alias `recomendado`; `manifests/catalog.json` + `manifests/aliases.json` (`pipelines/registry.py`: promote, rollback, SHA-256) are the source of truth for state and production; Prefect flow with 8 stages + rollback flow; real rollback on Render tested by Miguel (~25 s redeploy). Details: versioning.md, `docs/rollback.md`, `docs/relevo-r3.md`.

**Web (R4 + migration to Render, 2026-11-19):** `web/src/viewer-api.js` (contract 9.3 `api()`: `VITE_API_BASE_URL`, relative fallback, `X-Sesion` in `sessionStorage` key `warehouse-sesion`, `credentials: 'omit'`, 429 messages, «Despertando el servidor…» after 3 s, session-lost recovery); `web/src/api-client.js` (non-`/api` routes: `/catalogo`, `/version`, `/monitoreo`, `/evaluaciones`, nested error format); dialog «Modelos y experimentos» = API `/catalogo` (state, alias, executable) merged by `run_id` with static `web/public/modelos/catalogo.json` (hypothesis, changes, curves, MLflow link); any of the 20 executable models can be loaded, diagnosed (`/api/evaluate`, `certificado: false`) and officially evaluated (`POST /evaluaciones` + polling, progress bar, per-episode table, match against the manifest's registered evaluation); served-model chip (`/version` + `X-Modelo-Servido`), «Monitoreo» dialog (`/monitoreo`), mode badge, location tag (LOCAL / API LOCAL / EN LÍNEA), deep links `?modelo=<id>&cerrado=1&semilla=N` and `?catalogo=<id>`.

**Tests:** 373 Python tests pass (`-n 6 --dist loadfile`, ~2 min). Playwright: 25 web tests (23 pass + 1 skipped by design: generic PPO gone) against the local API; 5 key ones verified in production with real CORS at v1.0. How: workflow.md («Web and API», «Browser tests»).

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
- Teammates' prompts get pasted in (e.g. a prompt written for Miguel's Claude, or the web-migration task). Read the referenced doc first (`docs/api-contrato.md` "manda"); when the doc and the prompt disagree, follow the doc and say so. When a referenced file does not exist yet, stop and report instead of guessing its contract.
- The user wants one file per commit (or one coherent change), each change explained before committing, Spanish messages with the motive. Commit with explicit paths (`git commit -m ... -- <paths>`): a bare `git commit` also commits whatever deletions are already staged.
- Deploys are outward-facing: ask before deploying an unmerged branch to production; previews cannot reach Render (CORS), so the user chose to wait for the merge. Record every deploy in `docs/despliegue.md` and put release tags on the deployed commit.
- Long Playwright/pytest runs: run in background, log per-test progress to a file and answer "how long?" from the measured count and elapsed time.
