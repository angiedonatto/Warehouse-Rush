# Project status vs the brief, and the R3 handover (2026-11-18)

Snapshot written 2026-11-18 after PR #2 was merged into `main` (merge commit `da14120`; at that moment `main` and `dev/lis` had the same tree). Verify with `git log origin/main` before trusting it. The user's goal: **only R3 is missing**.

## Deliverables checklist (brief sec. 17 + rubric)

| Deliverable | Status | Where |
|---|---|---|
| Reproducible repo + README (install, run, variables, architecture, reproduction) | done | `README.md` (sections Arquitectura, Reproducir 1-8, Revisar modelos desde la web), `.env.example`, `requirements.txt`, `web/package-lock.json` |
| Env contract + sheet + three levels | done | `envs/CONTRATO.md` (v10), `docs/ambiente-v0.10.md`, `docs/niveles.md` (N1 `m1o`, N2 `m1`, N3 `m1b`) |
| Baselines, first model, evaluation | done | random 0% / heuristic 100% on every suite (`docs/resultados/eval/lineas-base-*`) |
| >= 4 configs with hypotheses, MLflow runs and states (incl. failed/rejected) | done | `docs/experimentos.md` (pre-registered), 94 runs on DagsHub, `estado` tag on each |
| Finalists x 3 seeds, comparison, budget | done | `pipelines/compare.py`, `configs/comparaciones/finalistas-m1-v1.yaml` (c3 vs e4, c3 chosen) |
| Recoverable models, manifests, artifact refs, SHA-256 | done | `manifests/` (82 with runs), DVC on R2 (`models/<run>.dvc`), MLflow registry |
| Degradation / intervention evidence | done | incident N3: `m1-c3-seed0` 98% -> 0% with gap (6,14) closed; `m1b-i1` intervention; `m1b-i1-seed1-best` recommended |
| Reserved final test | done (both used) | `test-final-m1-v1`, `test-final-m1b-v1` (gitignored; results only in manifests) |
| Web: catalog, comparison, load/evaluate, modes, model+env identity, deep links | done (R4) | `web/src/models-catalog.js`, `web/src/main.js`, `POST /api/evaluate` |
| Monitoring minimum (success per scenario, failure causes, inference latency/errors, served version) | done in the evaluate route; no continuous monitoring | `api/_viewer.py::evaluate_served` (`monitoring` block), `/api/health` (env version + Vercel commit) |
| Asset licenses | done | `docs/licencias.md` |
| **Orchestrated pipeline (Prefect/Airflow)** | **missing (R3)** | `pipelines/flow.py` does not exist; `dvc.yaml` only has the old stage `train_c0` |
| **Rollback documented and tested** | **missing (R3)** | no `docs/rollback.md`, no rollback test |
| Deployed URL serving the current version | done 2026-11-18 (Lis) | https://warehouse-rush-psi.vercel.app, Vercel project `warehouse-rush` in Lis's team `lis-team2`, commit `49b8463` (visible in `/api/health`, deployed with `--env WAREHOUSE_DEPLOY_COMMIT`); see `docs/despliegue.md` |
| Release tag `v1.0`, short report, final presentation | missing (whole team, after R3) | — |

## What R3 still has to do (concrete, reuse what exists)

1. **Prefect flow `pipelines/flow.py`** with the course's minimum sequence. Each task should call the code that already exists, not reimplement it:
   - `validate`: load the YAML, check schema, paths, `environment_version == envs.ENV_VERSION` and the layout hash (`pipelines/train.py` already resolves configs).
   - `test`: `python -m pytest tests -q -n 6 --dist loadfile` (280 pass).
   - `train_or_load`: `pipelines.train` (logs to MLflow via `pipelines/tracking.py::mlflow_run`; requires `MLFLOW_TRACKING_URI`) or load the weights with `dvc pull models/<run>.dvc`.
   - `evaluate`: `pipelines.evaluate.evaluate(...)` on the fixed suite (`configs/suites/`), saving per-case results.
   - `register`: write the manifest (`.claude/skills/warehouse-rush/scripts/write_manifests.py` pattern), DVC add/push, then `pipelines/registrar_modelos.py` (model registry `warehouse-<level>`, alias `recomendado`, idempotent by `model_sha256`).
   - `decide`: apply the criterion pre-registered in `docs/experimentos.md` / `configs/criterios.yaml`.
   - `publish`: `python -m pipelines.servir` (copies recommended weights to `models/servidos/`, writes `configs/modelos_servidos.json`) and `python -m pipelines.catalogo` (writes `web/public/modelos/catalogo.json`).
   - `verify_served`: `GET /api/health` and `GET /api/layout` (`models[].model_sha256`) must match the manifest.
   Prefect 3.8.8 is already pinned in `requirements.txt`. Record the decision "Prefect" in `docs/decisiones.md` (Prefect vs Airflow was still open).
2. **Rollback**: `docs/rollback.md` + a test. Production = `m1b-i1-seed1-best` (N3); rollback = `m1-c3-seed0` (N2), both served. A faithful test: mark the production model as not recommended in a temp copy of the manifests, run `servir`/`catalogo`, check the API serves only the rollback model with its sha256, then restore and check again. Also say how to roll back the web: redeploy the previous Vercel deployment/tag.
3. **Deploy**: DONE 2026-11-18 by Lis (new project, `api/requirements.txt`, deploy from a clean clone; see docs/despliegue.md). Original notes: `vercel` preview first (not `--prod`). Risks: `requirements.txt` is now the full frozen env (mlflow, dvc, prefect, torch...), and the Python function may exceed Vercel's size limit. If so, add a minimal API requirements file (numpy, gymnasium, torch CPU, stable-baselines3; `pyyaml` is not needed at import time because `pipelines/train.py` imports it inside functions) and point the function to it. Also time `POST /api/evaluate` there (about 10 s for 20 episodes locally, limit 60 s; the web asks for 10). Then record the deploy commit, and check `/api/health` returns `warehouse-v10` and the Vercel commit.
4. Then the team: tag `v1.0` on `main`, report, presentation.

## Facts R3 needs that are easy to get wrong
- Vercel is **not** auto-deploying from GitHub for this repo (no deployment statuses on commits). `vercel.json` has `git.deploymentEnabled: {"dev/naomi": false}` from Naomi's branch; keep it.
- The API is stateless (signed cookie per visitor, `WAREHOUSE_SESSION_SECRET` >= 32 chars must be set in Vercel). Routes are allow-listed in `api/_cloud.py::CloudHandler._dispatch`: **a new route must be added to that tuple** (the evaluate route was missing there once and only a browser test caught it).
- Served models run with the **web catalog** `trendy-27-v1`; training/evaluation (`make_env`) pin `legacy-18`. See env-versions.md.
- MLflow writes need a personal DagsHub token in `.env`; `pipelines/tracking.py::tracking_uri` refuses to train without `MLFLOW_TRACKING_URI` (set `MLFLOW_PERMITIR_LOCAL=1` only for deliberate local tests).
