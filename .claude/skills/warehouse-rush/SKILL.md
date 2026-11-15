---
name: warehouse-rush
description: Project knowledge for the Warehouse Rush MLOps final project (Universidad Externado, Visualización 2). Use for anything in this repo - the 4 team roles (R1 env, R2 experiments, R3 versioner/pipeline/API, R4 web), course requirements and rubric, versioning conventions (Git, DVC, MLflow, manifests, SHA-256), experiment design, run naming, env contract and its versions warehouse-v1 to v10, the walled-map campaign of 2026-11-14/15, behaviour cloning from the heuristic (pipelines/bc.py), the full experiment log (what was tried, what worked, what failed and why), how to run/evaluate/diagnose/document an experiment, reward-hacking checks. The user is R2 (Entrenamiento y experimentos) and has also been changing the environment on the team's instruction.
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

## Current state (2026-11-15, branch `dev/lis`, ~70 commits ahead of `origin/dev/lis`, nothing pushed; verify with `git log` and `git tag`)
**Environment:** `ENV_VERSION="warehouse-v10"` (ficha 0.10.0; tags `env/warehouse-v2` ... `env/warehouse-v10`). Only the **makeup mode** is trained: `Box(27)` observation, `Discrete(8)` actions, 25x19 warehouse, 6 racks x 3 shelf levels, battery 180, 400 steps. Reward coefficients are per-run YAML (`recompensa:`). Terms added after v5: v6 `lower_bonus` (removed in v7), v7 `carry_milestone`, v8 `face_bonus`, v9 `potential` (potential-based shaping, one weight) + training-only stagnation stop (`parada_estancamiento: N` in the YAML, `pipelines/train.py::StagnationStop`), v10 `potential_nav` (navigation weight inside the potential). **All of v8-v10 default to 0 / v9-equivalent, so a v10 config with none of them behaves exactly like v5-v7** (`m1-c2` reproduced `m1-c0l-seed0` bit for bit). Maps: `layout_v0.4.json` (walled: interior wall y=14, permanent gap x=20, closable gap x=6) and `layout_v0.5.json` (open). Levels `m1` (walled) and `m1o` (open), 3 random SKUs per episode. Details: [references/env-versions.md](references/env-versions.md).

**Focus since 2026-11-14: the walled map (`m1`, the course scenario), pure RL (no imitation).** Every open-map model (`m1o-e4l-seed0` 92%, `m1o-h0` 100%) scores 0/50 on the walled map without retraining. Headline results on `suite-m1-v1` (deterministic, seeds 10000-10049; heuristic 100%, 79.9 steps):
- **Best walled-map models (all `candidato`, none `recomendado`, each carried by one seed):** `m1-e4y-seed3` **100%** (e4 reward, 1 802 240 steps, stagnation stop), `m1-c3-seed0` **98%** (base reward: invalid -0.2, collision -1, default `progress` 0.3, no e4 terms, 1 802 240 steps, stop), `m1-e4x-seed2` 80% (e4, 1 802 240 steps, no stop). Successes take 87-94 steps.
- **Reliability is the problem, not the reward:** at 1 802 240 steps, **3 of 15 seeds** complete the mission (e4x 1/3, e4y 1/3, c3 1/5, c4 0/4); the e4 terms and the stagnation stop do not visibly change that rate. Failed seeds stall at different stages (idle, reach-and-face, load-but-never-deliver). At 606 208 steps **nothing** completes the mission on the walled map (e4l, c0l, c1, j1-j3: all 0%).
- **Potential-based shaping (v9/v10) failed in all 13 runs** (`p1`, `p2`, `q1`, `q2`, `s1`; W = 30/90/150, with/without scaled penalties, with/without navigation): 0/50 episodes ever reach a shelf cell, while the plain `progress` reward does in most seeds. Regression control `m1-c1`/`m1-c2` cleared the v9 code and the stop. Cause not established; the line is parked.
- **Latest (2026-11-15):** `m1-c4-seed1..4` (`c3` + `ent_coef` 0.01): 0/0/0/0%, criterion refuted, but entropy moves 3 of 4 seeds a stage further than their `c3` pair; `m1-c4-seed2` loads all 3 lines in 50/50 episodes and never delivers (tray down, carrying). **The bottleneck is now the delivery leg**, not discovery. 3 of 15 seeds succeed at 1.8M steps overall. Nothing in flight.
- **Pick up here (nothing in flight as of 2026-11-15 15:30).** The diagnosis after c4: entropy fixed discovery (3 of 4 seeds load; `m1-c4-seed2` loads all 3 lines in 50/50 episodes with 0 invalid, 0 collisions) but **0 deliveries in ~50 000 training episodes**. After the last pickup the target jumps to DELIVERY, ~15 BFS cells around the wall, and the only signal on that leg is `progress` 0.3/cell until +30/+50 at the end; the policy sits with the tray down and cargo aboard. Options the user was offered, in the order I would run them (each needs a pre-registered hypothesis in `docs/experimentos.md` first):
  1. **Continue `m1-c4-seed2`** from `models/m1-c4-seed2/model.zip` with `parent_run_id: m1-c4-seed2`, 1-2M more steps, same config (`parada_estancamiento` 100, `ent_coef` 0.01). Its dev return turned positive at 1.46M, so it may simply need time on the last leg. Config-only; ~105 min per 1.8M steps. Criterion: >= 50% on `suite-m1-v1`.
  2. **A delivery-leg signal that pays before the tray is down**: e.g. a one-off bonus for first reaching the dispatch approach cell (21,16) with cargo, or `progress` weighted higher only while the target is DELIVERY. New env version (v11) + ficha + contract + tests + scripted returns. `carry_milestone` (v7) does **not** count as tested for this: it requires the tray lowered first and was only run on seeds that never loaded (j2 = e4l-seed0 bit for bit).
  3. **`ent_coef` 0.01 on seed 0** (the 98% seed of c3) to learn whether entropy hurts a seed that already works. One run.
  4. **Declared seed selection** (best of N on a dev suite, validated on `test-final`) is the only route to a deployable model with today's evidence (`m1-c3-seed0`, `m1-e4y-seed3`).
- Open-map results (v5-v7, `suite-m1o-v1`): `m1o-e4l-seed0` 92% (seeds 1-2 0%), `g1` 94/0/0% rejected, `h0` (behaviour cloning) 100/100/100% (reference, not RL evidence), `h1` 88/92/100% rejected on collisions. Full tables and lessons: [references/experiment-log.md](references/experiment-log.md).

**Tooling:** tests **196 pass in ~30 s** with `-n 6 --dist loadfile` (pytest-xdist pinned in `requirements.txt`; the venv had no pip, bootstrapped with `ensurepip`), ~83 s serial; building an env costs 0.03 s (was 2.6 s before the `Layout.distance_field` fix of 2026-11-14). Four parallel 1 802 240-step runs take **~105 min** on this machine (~270 steps/s each); 606 208-step runs ~27 min. Manifests: 65+ in `manifests/`, all validated against `manifests/schema.json`. Weights exist **only locally** (`models/` git-ignored, no DVC remote).

**Not done / blockers for deployment:** no `recomendado` model; no finalists x 3 seeds; reserved `test-final` never run; weights not shared (no DVC remote); nothing pushed, no PR; web viewer/API not rebuilt for v3+; Prefect flow, `compare.py`, `callbacks.py`, N3 incident suite missing. Open items: [references/experiment-log.md](references/experiment-log.md) ("Open items").

## Working conventions with this user (learned in sessions)
- All work on `dev/lis`; Spanish commits and Spanish project docs; this skill is in English. Do not push unless asked. Commit **before** launching training; tag env versions.
- The user decides the experiments and gives exact reward values; implement exactly what is asked, flag assumptions (for example "open map = interior wall removed, racks kept", "3 SUBIR for shelf 3 because the stowed position is not a shelf", "bonus only with target DELIVERY") and correct course openly when a rule applies (a reward-function change bumps the version). When the user asks for two changes at once (v6: time + bonus), run the combination and one-change ablations so the effect can be attributed.
- For environment tests the user prioritizes **the environment working over the agent working**: test rules, contract and reward terms, not model quality.
- The user redirects quickly: it stopped the more-seeds runs to try behaviour cloning, and asked "how long left?" repeatedly. For time estimates **measure** (elapsed seconds of the process and `time/total_timesteps` in `docs/resultados/training/<run>/progress.csv`), never guess; for "is it done?" check the real state before answering. Mention that concurrent tests/scripts slow training (5 parallel runs ran at about 290 steps/s, not 540).
- When a pre-registered criterion fails on one condition, report the other numbers honestly but keep the verdict (h1: +62.7 pp but collisions failed; g1 sampled eval much better than deterministic). Exploratory diagnostics decided after seeing results never change the official status; say that explicitly and propose a new pre-registered criterion if the user wants it.
- Present results as tables with the measured facts first, then the decision by the pre-set criterion, then diagnosis, then limitations; separate measured facts from hypotheses; never claim learning from a single seed; say plainly when something failed or was not run.
- Explain in plain language when asked (the user asked for step-by-step descriptions of what the agent observes and does, and of the reward).
- When writing to the skill for the user: update SKILL.md (state), env-versions, experiment-log, workflow, and also the project memory snapshot.
