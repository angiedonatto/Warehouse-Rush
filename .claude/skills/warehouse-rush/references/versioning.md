# Versioning plan (R3 owns, everyone follows) - 30% of the grade

Goal: for any result we can say what changed, reproduce it, and restore an earlier version. Below, "DECIDE" marks items the team still has to agree.

## 1. Which tool versions what (from the Enunciado, sec. 03 "Librerías y responsabilidades" and sec. 10 "Versionar todos los elementos")
The brief fixes the tools; do not substitute (Hugging Face Hub, used in the prototype, is not in the brief).

| Tool (brief) | Responsibility (brief) | Evidence to deliver (brief) |
|---|---|---|
| **Git + DVC** | code/configuration, and identity of large artifacts | commits, tags, references, hashes |
| **MLflow** | runs, metrics, artifacts, model registry | accessible history and identified models |
| **Prefect or Airflow** (agree in class) | pipeline orchestration | executable flow and run log |
| **FastAPI + Uvicorn** | simulation/inference API | endpoints, model version, errors |
| **Vercel** | web publication | URL and deployment linked to Git |
| Stable-Baselines3 + PyTorch | policy training (PPO) | model, parameters, budget |
| Gymnasium | env interface | reset/step and documented contract |
| TypeScript + Vite | web app build | code and lockfile |

Per element (sec. 10 table), minimum version evidence and the tool that holds it:
| Element | Minimum evidence (brief) | Tool |
|---|---|---|
| Code | full commit + final release/tag | Git/GitHub |
| Environment | dynamics, sensors, actions, limits, dt, compatible reward | Git (`ENV_VERSION`, tag) + contract |
| Scenarios/data | maps, obstacles, distributions, seeds, suite | Git (suite YAMLs); offline data/demos via DVC |
| Configuration | versioned JSON/YAML + immutable snapshot per run | Git + MLflow artifact `config.json` (+ SHA-256) |
| Experiment | hypothesis, change, origin, budget, status | MLflow (params/tags) |
| Model | weights, hash, normalization, input/output contract | MLflow registry + DVC for large files + manifest (SHA-256) |
| Evaluation | cases, metrics, episode count, suite version | MLflow artifact `evaluacion.json` + suite id |
| Pipeline | validation, training, registration, publication code | Git + Prefect/Airflow flow |
| Deployment | commit, release, catalog, served version | Vercel (linked to Git) + catalog + `/version` |
Rule from the brief: large artifacts go to "the agreed storage" and must be recoverable. Catalog is derived from the MLflow registry plus consistent manifests. Keep: final checkpoint of each complete run and selected models until review; limit intermediate checkpoints with a documented policy.

## 2. Git
- Branches: `main` (protected, PR + 1 approval + passing test), `dev/<name>` per member, optional `feature/<topic>` off a dev branch. Prototype branch `experiment-1` is superseded: migrate and delete or rename.
- Protect `main` on GitHub: require PR, require review, no force-push.
- Commits in Spanish, conventional prefixes: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `refactor:`; say what and why. One role's folders per commit when possible.
- Folder ownership prevents conflicts: only edit your role's folders; ask the owner or open a PR for others'. `.gitattributes` / CODEOWNERS file mapping folders to owners (suggested).
- Tags (annotated): `v0.1` first full cycle (contract + baseline + first deploy), `v1.0` reproducible delivery. Environment tags `env/warehouse-v1`. Model tags optional `model/<run_id>`. Command: `git tag -a v1.0 -m "Entrega reproducible" && git push origin v1.0`.
- `.gitignore` must cover: `.venv/`, `node_modules/`, `.env`, `mlruns/`, `mlflow.db`, `*.npy`/`*.zip`/`*.pt` weights (tracked by DVC instead), `__pycache__/`, `dist/`, local training outputs, `configs/suites/test-final*` (reserved test). Keep `.env.example`.
- Never rewrite published history on `main`.

## 3. Python/Node reproducibility
Python 3.12 in `.python-version`; PyTorch CPU installed from `https://download.pytorch.org/whl/cpu` (document index), then `pip install -r requirements.txt` (one owner regenerates it; pin exact versions; keep torch out or documented separately). Node LTS in `.nvmrc`, `package-lock.json` committed, install with `npm ci`. README states both.

## 4. Configs
YAML per planned run in `configs/experiments/`; code never holds hyperparameters. At run start save an immutable resolved snapshot (`config.json`) and its **SHA-256**; log hash as param + tag. Hash over canonical JSON (sorted keys) so formatting does not change it.

## 5. DVC
- `dvc init` done (`.dvc/`). **Remote `r2` (default) = Cloudflare R2, S3 API**, bucket `mlops-final-project`, `region auto`, endpoint in `.dvc/config`; keys only in `.dvc/config.local` (git-ignored); needs `dvc-s3` (pinned). Decided 2026-11-15. Never commit or print remote credentials.
- **Retention policy:** each run folder `models/<run>/` is tracked by its own `models/<run>.dvc` and holds `model.zip` + `best/`; intermediate `checkpoints/` stay local only (`.dvcignore`). Top-level aliases (`models/ppo_orders*_seed*.zip`) are overwritten by later runs and are not tracked. `models/n1-c0-seed0` belongs to the `train_c0` stage in `dvc.yaml` (no `dvc.lock`), so it is not `dvc add`-ed.
- **Gotcha:** a plain `dvc push` once reported "Everything is up to date" and `dvc status -c` "in sync" with an empty bucket; push the targets explicitly (`dvc push models/*.dvc`) and verify by fetching into an empty cache.
- Track: model weights, VecNormalize stats, any offline data/demos. Pipeline stages in `dvc.yaml` with `deps`/`params`/`outs`; commit `dvc.lock`. Existing `dvc.yaml` runs the prototype `python -m warehouse_rush train`; rewrite for `pipelines/train.py --config ...` when migrated.
- Workflow: `dvc add models/<x>` -> commit the `.dvc` file -> `dvc push`. To restore: `git checkout <tag> && dvc pull`.

## 6. MLflow
- Persistent tracking server: **DagsHub** `https://dagshub.com/mamezquita/Warehouse-Rush.mlflow` (decided 2026-11-18; public read, write needs each member's DagsHub token in `.env`: `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`; load with `set -a; source .env; set +a`). `pipelines/tracking.py::tracking_uri` refuses to train without the URI (`MLFLOW_PERMITIR_LOCAL=1` = deliberate local sqlite). The 96 runs of the old local `mlflow.db` were copied by `pipelines/migrar_mlflow.py` (new run ids; tag `origen_run_id` = old id; map `docs/resultados/mlflow-migracion.json`; manifests carry `mlflow_run_id` = server id and `mlflow_run_id_local`); the old sqlite + `mlruns/` are a DVC snapshot (`mlflow.db.dvc`, `mlruns.dvc`), never committed raw. Model Registry: `pipelines/registrar_modelos.py` registers every `recomendado` manifest as a version of `warehouse-<level_id>` (tags `estado`, `model_sha256`, `manifiesto`, test final; alias `recomendado`). Previously: local `mlflow.db`/`mlruns/` (lost with the laptop). Tracking URI from env var `MLFLOW_TRACKING_URI`.
- One experiment per level: `warehouse-n1`, `warehouse-n2`, `warehouse-n3` (prototype uses a single `warehouse-rush`).
- Run name `<nivel>-<hipótesis>-seed<semilla>` e.g. `n2-c3-seed1`.
- Required **params**: resolved PPO params, level, seed, budget (steps), hypothesis, config_sha256.
- Required **tags**: `git_commit` (full SHA; also `git_dirty` true/false, refuse or flag dirty runs), `environment_version`, `config_sha256`, `nivel`, `hipótesis`, `parent_run_id` (or none), `tipo` (`referencia` | `candidato`), `estado` (`candidato` | `recomendado` | `rechazado` | `fallido` | `interrumpido`), `suite_id`, `runtime_ref`.
- Metrics: `train/*` per step; `eval/exito`, `eval/entregas`, `eval/choques`, `eval/tiempo_pedido` per eval step; final: real steps and minutes.
- Artifacts: `config.json`, model, normalization stats, `evaluacion.json`, curves JSON/PNG.
- Failed runs: status `fallido`, error text, tag "sin checkpoint disponible".
- Registry (done 2026-11-18): `warehouse-m1` v1 = `m1-c3-seed0`, `warehouse-m1b` v1 = `m1b-i1-seed1-best`, alias `recomendado`, version tags `estado`, `model_sha256`, `manifiesto`, `test_final`; `python -m pipelines.registrar_modelos` registers every `recomendado` manifest, idempotent by `model_sha256` (uploads a best checkpoint as `modelo_best/` after checking its hash). Never delete versions; add an `anterior` alias when promoting a new one.
- R3 provides `pipelines/tracking.py` so R2 does not duplicate this logic: `start_run(config_path, ...)`, `log_resolved_config`, `finish_run(status, ...)`, `register_model(...)`. Define its function signatures first week.

## 7. Manifest (`manifests/<run_id>.json`, one per recoverable model)
Required keys (from the course): `run_id`, `level_id`, `environment_version`, `git_commit`, `config_sha256`, `model_uri`, `model_sha256`, `normalization_uri`, `runtime_ref`, `evaluation_suite_id`, `seed`, `parent_run_id`.
Recommended extras: `created_at`, `author`, `estado`, `budget_steps`, `budget_minutes`, `obs_spec`/`action_spec` (order, dims, units, clipping) or pointer to `envs/CONTRATO.md@<commit>`, `rules_ref`, `optimizer_uri` + `timesteps` (if continuing is offered), `metrics_summary`, `results_uri` (`evaluacion.json`), `decision` and `decision_reason`, `schema_version`.
Rules: manifest is immutable once published; a change creates a new manifest/version; `model_sha256` must match the file at `model_uri` (verify on load and in CI); JSON schema in `manifests/schema.json` validated by a test and by the pipeline. Catalog `manifests/catalog.json` lists all manifests, the `recomendado` per level and the `anterior`.

## 8. Model package contents
Weights + SHA-256; obs/action spec; normalization + clipping; compatible env (version + code ref, package or image); rules in force; run, effective budget, seeds; suite and per-case results; origin (scratch/checkpoint); optimizer + counter if resumable. Storing only weights is not enough.

## 9. Environment versioning
`ENV_VERSION` constant in `envs/`, written to MLflow tag and manifest. Any change to obs order/units/ranges, actions, dt, physics or reward -> bump version. Keep old env code recoverable (git tag `env/warehouse-v1` + installable package or Docker image as `runtime_ref`) so old models still evaluate with their original rules, or ship a validated adapter.

## 10. Evaluation suites
`configs/suites/{dev,suite}-nX-v1.yaml` list episodes + seeds (dev 1000-1009, suite 10000-10049, test-final reserved and never public). Suites are immutable: change = new id (`-v2`). `evaluacion.json` records `suite_id`, episode count, per-episode results.

## 11. Pipeline (Prefect, `pipelines/flow.py`)
Stages = course minimum sequence (see roles.md). Each stage writes status + evidence to MLflow/local log. Idempotent: rerun reuses or creates an explicit new version. Tasks: `validate`, `test`, `train_or_load`, `evaluate`, `register`, `decide`, `publish_catalog`, `verify_served`.

## 12. Deployment and rollback
- **Serving (done 2026-11-18):** `python -m pipelines.servir` copies every `recomendado` manifest's weights compatible with `ENV_VERSION` to `models/servidos/<model>.zip` (sha256 checked; never overwrites different content) and writes `configs/modelos_servidos.json` (identity, exact eval config: layout, orders, reward overrides, `catalogo_evaluacion`/`catalogo_web` and the catalog diagnostic). The API verifies sha256, layout hash and env version at load. `python -m pipelines.catalogo` writes `web/public/modelos/catalogo.json` + reduced curves from manifests + configs + MLflow ids (public read). Rerun both whenever a manifest changes, then `npm run build`.
- Vercel linked to GitHub, deploys tied to commits; record deploy commit and tag in the catalog; `/version` (or `/health`) endpoint on the API returns env version, model version, git commit.
- Rollback = point catalog `recomendado` back to `anterior` (alias change + publish catalog) and redeploy previous Vercel deployment/tag if the web changed. Write `docs/rollback.md` and **test it** (course requires a rollback test, with evidence).
- Monitoring minimum: success per scenario, failure causes, inference latency/errors, served version.

## 13. Decision log and docs
`docs/decisiones.md` (date, author, reason), `docs/experimentos.md` (R2), `docs/ambiente-v0.1.md` (R1), `docs/rollback.md`, README with install/run/vars/architecture/reproduction, `.env.example`, license notes for assets.

## Setup order (R3 week one)
1. Agree remotes: MLflow host, DVC remote, API host (with the teacher). 2. Protect `main`, add CODEOWNERS, PR template (checklist: tests pass, decision logged, versions bumped). 3. Fix `.gitignore`, `.python-version`, `.nvmrc`, pinned `requirements.txt`. 4. Write `manifests/schema.json` + example + validation test. 5. Write `pipelines/tracking.py` API and hand it to R2. 6. Hash helper (`sha256_file`, `sha256_config`). 7. Skeleton `dvc.yaml` and `flow.py` against R1's minimal env. 8. Catalog + `/version` endpoint. 9. Rollback doc + test on a dummy model. 10. CI (GitHub Actions: pytest + schema validation) if allowed.
