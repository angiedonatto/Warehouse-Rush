# How we work in this repo (commands, protocol, pitfalls)

Branch: `dev/lis` (all work goes here; `main` only by PR with review). Not pushed unless the user asks. Commits in Spanish (`feat:`, `fix:`, `docs:`, `test:`, `chore:`), end with the attribution line the session requires. Git identity is not configured globally: `git -c user.name=Lis -c user.email=<user email> commit ...` (use the address already in the user's project memory; never send it to external services). Python 3.12 venv at `.venv` (built with uv); run tools as `.venv/bin/python`.

## Commands
| Task | Command |
|---|---|
| Full tests (about 1.4 min serial, **about 30 s in parallel**: `.venv/bin/python -m pytest tests -q -p no:cacheprovider -n 6 --dist loadfile`; 196 pass; it was about 9 min before the 2026-11-14 BFS speed-up) | `.venv/bin/python -m pytest tests -q -p no:cacheprovider` (add `--junitxml=docs/resultados/pytest-warehouse-vN.xml` to keep the report) |
| Reward/config tests only (about 40 s) | `.venv/bin/python -m pytest tests/test_reward_config.py -q -p no:cacheprovider` |
| Write manifests + MLflow `estado` for finished runs | `.venv/bin/python -I .claude/skills/warehouse-rush/scripts/write_manifests.py <decisions.json>` (see the script docstring; validates against `manifests/schema.json`) |
| Train a run | `.venv/bin/python -m pipelines.train --config configs/experiments/<file>.yaml` (writes `models/<run>/`, `docs/resultados/training/<run>/`, logs to MLflow `warehouse-<nivel>`; fails if the run already exists; rejects a config whose `environment_version` differs from `ENV_VERSION`) |
| Evaluate with the run's own map and reward | `.venv/bin/python -I .claude/skills/warehouse-rush/scripts/eval_run.py <run>` |
| Behaviour cloning (imitate the heuristic, saves a PPO-compatible model; use it as `parent_run_id` of a PPO config): `.venv/bin/python -m pipelines.bc --config configs/experiments/m1o_h0_bc_seed0.yaml` (about 10 min, mostly demo generation) |
| Stochastic diagnostic (sampled actions, 3 repeats): `.venv/bin/python -I .claude/skills/warehouse-rush/scripts/eval_stochastic.py <run>` (writes `stochastic.json`; diagnostic only, official eval is deterministic) |
| Diagnose a policy (final states, key-state probabilities) | `.venv/bin/python -I .claude/skills/warehouse-rush/scripts/trace_policy.py <run>` |

`pipelines.evaluate.evaluate(...)` does **not** infer the map or reward from the model: pass `layout_path=` and `reward_overrides=` (the scripts read them from `metadata.json`).

## Experiment YAML keys
`id, hipotesis, nivel, environment_version, parent_run_id, seed, presupuesto_pasos, layout (optional path), recompensa (optional coefficient overrides), ppo{...}, evaluacion{intermedia, cada_pasos, final}`. Run name = `<nivel>-<id>-seed<seed>`, so **one YAML per seed**. Reward keys (v7): `pickup, delivery, completion, progress, time, battery, collision, invalid_interaction, distance, manhattan_progress, height_mismatch, carry_milestone` (`lower_bonus` was v6 only and is rejected now; unknown keys, negative rewards, time >= 0 or positive penalties are rejected). Levels in `configs/niveles.yaml`: `n1-n3` (v1 history), `m1` (walled map, 3 random SKUs), `m1o` (open map, 3 random SKUs). Suites are immutable: `dev-*` seeds 1000-1009, `suite-*` seeds 10000-10049; a new map or level means a new suite id.

## Protocol for every experiment (what the teacher and R3 grade)
1. **Hypothesis before training**, in `docs/experimentos.md`: change (one dimension), what would refute it, decision criterion from `configs/criterios.yaml` (adopt if success beats the baseline by >= 5 pp without collisions rising >10%), secondary descriptive metrics, runs table, budget table with "(pendiente)". Include **scripted-behaviour returns measured before training** when the change is a reward (idle at base / approach and idle / pick and stall / full order) to catch perverse incentives.
2. Create the configs; assert the PPO block is identical to `c0_baseline_n1.yaml` (`diff` of the `ppo:` block) unless the hypothesis is about it; add a test that pins what differs.
3. Run the tests. If the **code** changed: full suite, update `envs/CONTRATO.md`, add `docs/ambiente-v0.N.md`, `docs/decisiones.md`, bump `ENV_VERSION`/`__version__` in `envs/__init__.py`, commit, **annotated tag** `env/warehouse-vN` (`git tag -a env/warehouse-vN -m "..."`).
4. **Commit before training** so `git_commit` in MLflow/metadata is the real code. Launch runs in parallel (below).
5. After training: evaluate on the suite, diagnose with `trace_policy.py`, write `manifests/<run>.json` (schema `manifests/schema.json`: run_id, level_id, environment_version, git_commit, config_sha256, model_uri, model_sha256, normalization_uri, runtime_ref, evaluation_suite_id, seed, parent_run_id; plus estado, budget, reward, layout, results_uri, decision, decision_reason), validate it with `jsonschema`, set the MLflow tag `estado` (`candidato` / `recomendado` / `rechazado` / `fallido` / `interrumpido`), fill the budget table (real steps and minutes), add the results section (facts, decision by criterion, diagnosis, limitations), add a `docs/decisiones.md` row, commit.
6. Keep failed/rejected runs and their evidence. Do not change reward/criteria after seeing results; a new idea is a new run (and a new version if it changes the reward).
Valid `level_id` values in the schema: `n1, n2, n3, m1, m1o` (R3 owns the schema: tell them when adding one).

## Launching runs in parallel
```bash
for f in cfgA cfgB cfgC; do
  (nohup .venv/bin/python -m pipelines.train --config configs/experiments/$f.yaml \
     > /tmp/<scratch>/$f.log 2>&1; echo "exit $?" >> /tmp/<scratch>/$f.log) &
done
```
Observed: the machine has 16 cores and 7.6 GB RAM; 4-5 runs in parallel each train at about 520-550 steps/s (a lone run about 540); 204 800 steps take 8-10 min, 606 208 steps 24-26 min. Training is single-threaded and **deterministic** (same config and seed -> same model; `m1-c0b` reproduced `m1-c0` exactly). Runs launched together in the same instant can record `git_dirty: true` only because sibling runs created untracked output folders; no tracked file changed. State that in the manifest (`git_dirty_note`) rather than hiding it. Concurrent writes to `mlflow.db` produced no lock errors in practice.

## Behaviour cloning (`pipelines/bc.py`)
`.venv/bin/python -m pipelines.bc --config configs/experiments/m1o_h0_bc_seed0.yaml [--workers 7]`. The YAML is a normal experiment YAML plus a `bc:` block (`episodes`, `val_episodes`, `noise` list, `epochs`, `lr`, `batch_size`) and `presupuesto_pasos: 0`; the `ppo:` block fixes the network (and must match the fine-tuning config). It collects heuristic demonstrations (seeds 40000+, validation 50000+; noise episodes inject random actions but keep the heuristic's action as label), trains actor (cross-entropy) and critic (returns), writes `models/<run>/model.zip` + `metadata.json` (with `bc.fit` accuracies and `demos_sha256`) and logs MLflow. Then a PPO config with `parent_run_id: <bc run>` continues training (`parent_model` path in `train.py`; run-name pattern `<nivel>-<id>-seed<s>`). Evaluate the BC-only model with `eval_run.py` like any other run. Takes about 10 min per run, almost all demonstration generation (identical for every seed: caching by config hash would save it). BC hyperparameters may be tuned only on validation accuracy (rule fixed beforehand), never on the suite. The expert is privileged (BFS + env internals): the result is a reference, not RL evidence.

## Stopping runs and long jobs
- Background `python` jobs ignore SIGINT; stop them with `kill -TERM <pid>` (by PID, never `pkill -f` with a pattern that matches your own shell: it returned exit 144). The tracker does not get to mark them, so set the MLflow tags yourself (`estado=interrumpido`, `sin_checkpoint=true`, `set_terminated(run_id, "KILLED")`) and record the cancellation in `docs/experimentos.md` and `docs/decisiones.md`. The run folder name then exists (`mkdir exist_ok=False`): to re-run, remove the partial `models/<run>` and `docs/resultados/training/<run>` and delete the MLflow run.
- Wait for jobs with a background `until` loop that exits when the logs show `exit N` (you get a notification), not with foreground `sleep`.
- Steps/second drops when several jobs share the 16 cores or the tests run at the same time (5 parallel runs: about 290 steps/s; 3 parallel: about 340; the first sweeps reached 540).
- `train_ppo` copies each final model to `models/ppo_orders<orders>_seed<seed>.zip/.json` (an alias overwritten by the next run with the same orders and seed). Tests that train must use a unique seed (987 in `tests/test_bc.py`) so they do not overwrite or delete these aliases.

## Pitfalls we hit
- A manifest/test that loads a config with `load_config` fails for older versions (it rejects `environment_version` != current). Read finished history configs as raw YAML.
- `pkill -f "pytest tests"` inside the same shell kills that shell (exit 144); stop background jobs with the task tool instead. `sleep` is blocked in the foreground: wait with a monitor/until-loop on a log line.
- Rewriting `manifests/schema.json` with `json.dump` reformats the whole file (noisy diff): edit the one enum line with `sed`.
- `models/*` is git-ignored: **weights exist only locally** (including the only model that completes the mission, `models/m1o-e4l-seed0/model.zip`, 188 KB, sha256 in its manifest). DVC remote is undecided; `experiment-001` is the only snapshot kept in Git by exception.
- `info["reward_components"]` keys equal the `RewardConfig` field names; adding a reward field changes both places.
- `pipelines/evaluate.py` needs `layout_sha256` (and `rewards`/`simulation`) in the run's `metadata.json`; `bc.py` writes them now (h0 runs were patched after training and say so in `patched_fields`).
- The web viewer (`web/`, `api/_viewer.py`, `api/_cloud.py`) was relocated and tested for v2 but **not rebuilt or tested against v3-v5**; its action mapping uses the v2 names.

## Docs to touch per change (all Spanish except this skill)
`envs/CONTRATO.md` (frozen contract), `docs/ambiente-v0.N.md`, `docs/decisiones.md` (date, author lis, change, reason), `docs/experimentos.md` (hypothesis before, results after), `docs/modelo-actual.md` (note at top), `README.md`/`CLAUDE.md` (when the headline changes), this skill.

## Speed notes (2026-11-14)
- Building an environment used to cost about 2.6 s: `Layout.free()` rebuilt the wall/rack/obstacle sets on every neighbour check (about 41 000 times per build, inside the BFS distance fields). `Layout.distance_field` now builds the set once (about 0.03 s per build, 87x); `tests/test_layout_perf.py` pins it against the old slow implementation on every layout, station and blocked state. This is what made `test_cloud_makeup_roundtrip_and_inventory_retention` take 182 s (the stateless cloud API builds a fresh environment per request) and what made scripts that call `make_env` per episode (`eval_run.py`, `eval_stochastic.py`, ad-hoc diagnostics) slow. Training itself builds its environments once, so training speed (about 370-540 steps/s) did not change.
- `pytest-xdist==3.6.1` (and `execnet==2.1.2`) are now in `requirements.txt`; the project venv had no `pip`, so it was bootstrapped with `.venv/bin/python -m ensurepip`. Run `-n 6 --dist loadfile` (6 workers: 196 pass in about 29 s even with 4 training runs using the CPU). Keep `--dist loadfile`: tests that train use a fixed seed and write to `models/ppo_orders3_seed987*`, so every test file must stay in one worker. It is not forced in `pytest.ini` so a teammate without xdist can still run `pytest tests -q`.

## Timings and the laptop (2026-11-15)
- 606 208-step runs: ~27 min (3-4 in parallel). 1 802 240-step runs: **~105 min** with 4 in parallel on an idle machine (~270 steps/s each; the 80-90 min estimate was wrong twice). Steps/s is read from `time/total_timesteps` in `docs/resultados/training/<run>/progress.csv` (mtime = still alive).
- **WSL2 laptop sleep freezes training** without killing it: `ps -o pid,etime,time,%cpu -C python` shows real CPU time; `metadata.json` `duration_seconds` then overstates the run. Note it in the manifest (`budget_minutes`) and `docs/experimentos.md`.
- Tell the user up front when the request means > 1 h of training; they ask "how long left?" often: answer with measured steps and a finish clock time.

## Manifests (how they were written in the 2026-11-14/15 campaign)
`scripts/write_manifests.py` takes a JSON `{run: {"estado": ..., "reason": ..., "config": "<yaml basename>"}}`, templates the manifest from an existing one, fills git commit, sha256 of config and model, budget from `metadata.json`, the suite evaluation summary, `reward`/`reward_overrides`/`stagnation_window`, validates it with `jsonschema` and sets the MLflow tag `estado`. The decision reason must state the numbers (success, reach/face/raise/load, collisions, invalid, training successes) and the pre-registered criterion it was judged by.

## MLflow on DagsHub (2026-11-18)
- Load credentials before training: `set -a; source .env; set +a` (`.env` has `MLFLOW_TRACKING_URI=https://dagshub.com/mamezquita/Warehouse-Rush.mlflow`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` = personal DagsHub token; never print it). Without the URI `pipelines/tracking.py::tracking_uri` raises (`MLFLOW_PERMITIR_LOCAL=1` = deliberate local sqlite).
- Migration of the old local history: `python -m pipelines.migrar_mlflow [--solo <run>]` (idempotent via tags `origen_run_id` / `migracion=completa`), then `--manifiestos` to rewrite manifest ids. Deleted local runs are not copied.
- Reading is public (no token): useful for `pipelines/catalogo.py`.

## Web and API (2026-11-18)
- Publish models to the web: `python -m pipelines.servir` then `python -m pipelines.catalogo`, then `npm run build --prefix web`.
- API routes: `GET health|layout|state`, `POST reset|step|evaluate`. **Cloud mode allow-lists routes in `api/_cloud.py::CloudHandler._dispatch`; add new routes there** (and in `api/_viewer.py::ViewerHandler.do_POST` for the local viewer).
- Two servers, two kinds of web tests: the local viewer (`python -m pipelines.cli view --no-open`, port 8080, one shared session) is what most Playwright tests expect (they set state through `request` and read it in `page`); the cloud mode (`python -c "from api._cloud import preview; preview(8090)"`, per-visitor signed cookie) is what Vercel runs. Run `npx playwright test` in `web/` with `WAREHOUSE_TEST_URL=http://127.0.0.1:<port>` for the cloud mode.
- Test screenshots go to `SHOT_DIR` (default `web/test-results/capturas`, gitignored). Viewer tests also overwrite `docs/resultados/viewer-*.png`: `git checkout` them unless you mean to update them.

## Browser tests in this WSL without sudo
Chromium needs `libnss3`, `libnspr4`, `libasound2`. Download and extract them locally, then point Playwright at the installed Chromium:
```
mkdir -p $SCRATCH/libs/debs && cd $SCRATCH/libs/debs && apt-get download libnss3 libnspr4 libasound2t64
for d in *.deb; do dpkg -x "$d" $SCRATCH/libs/root; done
export LD_LIBRARY_PATH=$SCRATCH/libs/root/usr/lib/x86_64-linux-gnu
export CHROMIUM_PATH=$HOME/.cache/ms-playwright/chromium-1148/chrome-linux/chrome
cd web && npx playwright test
```
(`playwright.config.js` reads `CHROMIUM_PATH`; the bundled headless shell version 1248 is not installed.)

## Pitfalls added 2026-11-18
- A unit test that calls `CloudAPI.handle` directly does not exercise the HTTP route allow-list; keep a real-HTTP test (`tests/test_served_models.py::test_evaluate_route_over_real_http`).
- Teammates' tests may encode an older env (Naomi's assumed lift phases `raising`/`lowering`, removed 2026-11-13). Adapt them to the documented change, keep their intent, comment why.
- Reusing a teammate's CSS class for a new component can break their strict locators (`.catalog-dialog` matched two dialogs). Copy the rules to a new class instead.
