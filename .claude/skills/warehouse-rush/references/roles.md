# Roles and cross-role requirements

Team agreements (fixed day 1, from the team guide):
1. Branches: each member works on `dev/<name>`; `main` only via pull request with one approved review and a working test.
2. Env contract frozen in `envs/CONTRATO.md` (R1). Changes bump version, new model family.
3. R1 ships a **minimal env with the final contract first** (simple rules ok) so R2/R3/R4 don't wait for full physics.
4. Python 3.12, PyTorch CPU, frozen `requirements.txt` (one person generates the final one; others `pip install -r` after PyTorch). Node LTS + `package-lock.json`.
5. Run names: `<nivel>-<hipótesis>-seed<semilla>` (e.g. `n1-baseline-seed42`).
6. Commits in Spanish: `feat: agrega manifiesto con SHA-256`, `fix: ...`, `docs: ...`.
7. Never in Git: `.venv/`, `node_modules/`, `.env`, local `mlruns/`, big weights (weights go via DVC or MLflow artifact store).
8. Every technical decision goes to `docs/decisiones.md` with date, author, reason (feeds the defense).

## R1 · Environment and rules
Gymnasium env: map, physics, sensors, reward, terminations, levels N1-N3, closed-aisle incident. Folders `envs/`, `tests/`, `docs/ambiente-v0.1.md`. Deliver: documented reset/step contract, rule tests, env sheet.
Level design: N1 base mission (1 order); N2 more decisions (3 orders, routes/obstacles); N3 demanding operation (closed aisle). New obs/action dims = new model family.

## R2 · Training and experiments (user's role)
See [r2-experiments.md](r2-experiments.md).

## R3 · Versioner, pipeline, API
Persistent MLflow, DVC, SHA-256 manifests, model catalog, Prefect flow, FastAPI, rollback. Folders `pipelines/flow.py`, `pipelines/registry.py`, `pipelines/tracking.py`, `manifests/`, `api/`, `dvc.yaml`. Full spec: [versioning.md](versioning.md). Pipeline minimum sequence (course): validate config/paths/schema/env compat -> run rule/obs/action/termination tests -> train candidate or load compatible checkpoint -> evaluate on agreed suite saving per-case results -> register artifacts and model with hashes and provenance -> apply selection/rejection criteria -> publish catalog and recommended-model reference -> verify the version actually served and be able to restore the previous one. Each stage leaves state and evidence. Rerun may reuse the same artifact or create an explicit new version, never silently overwrite.
API (FastAPI+Uvicorn, HTTPS, CORS for the Vercel origin): catalog, load model, evaluate, episodes; reports model version and errors.

## R4 · Web and deploy
Vite + TypeScript + Three.js in `web/`; Vercel with Root Directory `web`, build `npm run build`, output `dist`, `VITE_API_BASE_URL` pointing to the real HTTPS API (VITE_ vars are public, no secrets), `.env.example`. UI must show: level and env, hypothesis, changes vs baseline, run and seed, steps and time, MLflow state (candidate/recommended/rejected/failed/interrupted), load/evaluate/compare buttons, episode, active phase/objective, reward, failure causes, model and env version. Clearly label mode: manual / random / reference / evaluation / training. Deep links and reload must work; no localhost in production.

## What each role needs from the others (requirements to make the team work)
| From -> To | Requirement |
|---|---|
| R1 -> all | `envs/CONTRATO.md` (order, units, ranges of obs/action, scaling/clipping, dt, physics step), minimal env early, `envs/heuristica.py` rule controller, env version string, tests, notice when reward allows exploits |
| R1 -> R3 | Env importable as package or recoverable image (`runtime_ref`), version constant exported (e.g. `ENV_VERSION = "warehouse-v1"`), deterministic given seed |
| R1 -> R4 | API-friendly state/telemetry dict per step (positions, orientation, order, load, battery, reward parts, termination cause) |
| R2 -> R3 | `run_id`s of selected models, `configs/criterios.yaml`, per-episode `evaluacion.json`, finalist decisions |
| R2 -> R4 | Metrics and curves as JSON (training and eval curves separate) for catalog and charts |
| R3 -> R2 | `pipelines/tracking.py` (start run with params, tags, config SHA-256, git commit, env version; log artifacts; set status), manifest format, persistent MLflow URI, experiment naming |
| R3 -> R4 | Stable API contract (OpenAPI), catalog JSON schema, HTTPS URL, CORS config, served-version endpoint |
| R4 -> R3 | Production origin(s) for CORS, deployment commit to record |
| all | Docs in `docs/decisiones.md`; PR reviews; same Python/Node versions |

## Versioner (R3) first-week checklist
See [versioning.md](versioning.md) section "Setup order".
