# Course requirements (Enunciado, 30 Oct 2026)

Universidad Externado de Colombia, Departamento de Matemáticas, Visualización 2 (Grupos A y B), docente Julián Zuluaga. Counts as "Proyecto 3 - Pipeline completo", 30% of the course per the registry (teacher may adjust the rubric). Defense date/time announced later; milestone dates in the guide are not new calendar dates.

## Product
A working URL (Vercel), a reproducible repo, an experiment registry, a set of recoverable models. The teacher must not install a server to open the delivery; backend/registry must stay up during review.

## Mandatory deliverables
- Reproducible repo + README: install, run, variables, architecture, reproduction.
- Environment contract and difficulty levels documented; baselines, first model, evaluation.
- Experiments in MLflow with hypotheses, candidates, comparison; failed/interrupted/rejected kept.
- Model catalog with manifests and artifact references; selected finalists and budget used.
- Pipeline, degradation/intervention evidence, rollback test.
- Deployed web (Vercel) + defense.

## Environment/learning concepts to respect
- Gymnasium: `reset()` / `step()`; `terminated` (mission success/failure) vs `truncated` (external step budget); log both.
- UI must say whether the animation is manual control, rule, evaluation or training. Animation speed must not change rules or physics step.
- Reward is a versioned function, not assigned by hand per move.
- Train exploration vs deterministic eval: report both curves separately.
- Three levels: N1 base (baselines, first model, evaluation), N2 more decisions (hypothesis, candidate, comparison), N3 demanding (degradation, intervention, recovery). New obs/action dims -> new compatible model family. Points of different missions/rewards are not comparable.
- Do not implement PPO from scratch (SB3 PPO). Small MLP on numeric observations; pixels out of scope.

## Versioned elements (minimum evidence)
Environment (dynamics, sensors, actions, limits, dt, reward) · scenarios/data (maps, obstacles, distributions, seeds, suite) · config (JSON/YAML + immutable per-run snapshot) · experiment (hypothesis, change, origin, budget, MLflow state) · model (weights, hash, normalization, I/O contract) · evaluation (cases, metrics, episode count, suite version) · pipeline code · deployment (commit, release, catalog, served version). RL has no static dataset, so version the generator, distributions and scenarios. Offline data/demos go through DVC.

## Model package (mandatory contents)
1 weights + SHA-256 · 2 order/dimensions/units of obs/actions, scaling, clipping · 3 compatible env (version and code, package or recoverable image) · 4 rules in force · 5 run, model, effective budget, seeds · 6 suite and per-case results · 7 origin (from scratch or checkpoint) · 8 optimizer and counter if continuing training is offered.
Keep the final checkpoint of each complete run and selected models until review ends; limit intermediate checkpoints with a documented policy. A run that failed before weights appears with diagnosis and status "sin checkpoint disponible".

## Comparing with evidence
Random + rule + learned baselines · concrete hypothesis, change one dimension · compatible env, comparable budget, recorded seeds · evaluate frozen model, keep per-episode results · compare success, failures by cause, duration, resources, latency · decide: select / reject / restore previous. **Three training seeds** for finalists; distinguish independent trainings from eval episodes; reserved final test stays outside parameter tuning.

## Pipeline, monitoring, recovery
Executable, orchestrated by Prefect/Airflow (agree in class). Controlled incident: perturb (here: closed aisle), measure before/after, propose intervention (accept or reject by evidence, keep the candidate). Minimum monitoring: success per scenario, failure causes, inference latency/errors, served version. Rollback must be documented and tested. Updating the web or registering a candidate is not promoting it.

## Deployment checks (Vercel)
`npm ci && npm run build` locally; Root Directory `web`; env vars per environment; `.env.example` without secrets; HTTPS API with CORS for the frontend origin; no localhost/127.0.0.1 in production; models and scenarios load without personal folders; old and recommended model both evaluable with correct contracts; deep links and reload work; check from another window/device; record deployment commit. Vercel Functions have time limits; Daemons are beta and need external persistence; auxiliary infra is agreed with the teacher (no paid service assumed).

## How the teacher reviews
Opens the web, picks a historical run, checks its identity, loads the model, runs an evaluation; asks to compare compatible candidates, explain failures, rebuild an evaluation from the release, restore a previous version.

## Defense script
Problem, mission, decisions, limits · levels · hypotheses tested (improved and worsened) · demo of historical and recommended model from Vercel · incident, recovery, rollback · cost, limitations, next hypothesis. Keep the reserved test set and any secrets out of the public repo; document asset licenses.

---
# Additional brief details (second pass)

## Warehouse Rush as the brief describes it (sec. 05)
Pick a package and deliver it at another station. Actions: movement + simple interaction. Observe obstacles, active objective, load state. Pickup may trigger by **proximity and stability**; **no articulated arm needed**. Reward milestones **once** and the correct delivery. Add restricted routes or a **blocked aisle** to test recovery. The brief's examples guide design but do **not** replace ranges, units and thresholds the team agrees per mission. The teacher's crane demo is only a reference, not a required scenario.

## Environment sheet (ficha del ambiente) must define (sec. 02)
Units, ranges, valid actions, physics step, decision frequency, success, failures, truncation, simplifications. Dynamics may be analytical or use a physics engine. Animation speed never changes rules or physics step.

## Levels (sec. 06)
- Keep earlier levels accessible in the product. A harder level does not oblige an old model to solve it. If dims or meaning of obs/actions change -> new compatible model family.
- Document **what new decision the agent must make** and **how difficulty is measured**. Graphics effects only represent the scenario; evaluable complexity comes from rules, constraints, operating conditions.
- Keep at least **four configurations with identified hypotheses** and evidence from **all three levels**. Performance thresholds and budget are agreed per world; reward points of different missions are not comparable.

## Algorithm choice (sec. 03)
PPO (SB3) is the reference. Other algorithms (e.g. tabular Q-learning, which the current prototype uses) need **justification and compatibility with the world's actions**; tabular Q-learning suits small discrete spaces, and discretizing a continuous system requires documenting the resolution loss. Small MLP on numeric observations is the starting point; learning from pixels is a different scope.

## Repo and Python setup (sec. 07)
Suggested layout: `envs/ configs/ pipelines/ tests/ web/ manifests/ docs/ requirements.txt README.md`. Verify Python availability/permissions. Windows uses `.venv\Scripts\python.exe` directly (no PowerShell script activation); Linux/macOS `python3 -m venv .venv` and `.venv/bin/python`. PyTorch CPU index (`https://download.pytorch.org/whl/cpu`) applies to Linux/Windows; macOS uses its official install. Document the procedure and index used. Keep `requirements.txt`, Python version and rebuild instructions. Reproduce = install PyTorch CPU as documented, then `pip install -r requirements.txt`. `.venv` is never in Git. The final README must reflect the procedure the team **actually verified**.

## Web build order (sec. 08)
Node LTS compatible with the installed Vite; **record both versions**. Create with `npm create vite@latest web -- --template vanilla-ts`, `npm install three`, `npm install -D @types/three`; later reproduction uses `npm ci` from `package.json` + `package-lock.json`. If `web/` exists, extend it. Scene parts: Scene, Camera, Renderer (WebGL), Mesh, lights/shadows (include a **light mode**), render loop (draws and interpolates, never redefines dynamics). Connect in order: (1) render a fixed state, (2) manual control and check collisions, sensors, terminations, (3) connect the policy. If Python is authority, the API returns positions/telemetry; if a JS/Node physics core is shared with the browser, validate that training and evaluation give equivalent transitions (Rapier is optional). Exporting a network to the browser does not move the Python env. Show episode, active phase/objective, reward, failure causes, model and env; label mode (manual/random/reference/evaluation/training).

## Git flow example (sec. 09)
`git status` -> `git switch -c feature/...` -> `git add <files>` -> `git diff --staged` -> `git commit -m ...` -> `git push -u origin ...`. Integrate by review plus a working test. Stable milestone: `git tag -a v1.0 -m "Entrega reproducible"` and `git push origin v1.0`. Deployment and manifests must identify the corresponding commit. Keep in Git: config files, lockfiles, DVC references, manifests.

## Architecture (sec. 15)
| Layer | Where |
|---|---|
| Web, static assets, catalog, comparison | Vercel |
| Simulation/inference | HTTPS API (when Python is authority); browser alternative must be validated |
| Training | team PC or a shared resource validated beforehand |
| MLflow/registry | persistent, recoverable storage |
Must work for the teacher from the delivered URL during the review period.

## Final package (sec. 17)
Vercel URL + repo with identifiable release/tag · README (install, run, variables, architecture, reproduction) · env sheet and three levels documented · four configs with hypotheses and MLflow runs/states · recoverable final models, normalization, manifests, artifact refs · per-case evaluations, finalist comparison, budget used · pipeline, degradation/intervention evidence, rollback test · **short report** (decisions, results, limits, contributions) · **final presentation**. Claims about learning must rest on mission metrics and documented conditions; a chosen demo does not replace evaluation.

## Milestones (sec. 18) - partial dates announced in class
1 Reproducir: contract, baseline, first run, initial deploy · 2 Experimentar: levels, hypotheses, catalog, historical models · 3 Operar: pipeline, comparisons, degradation detection · 4 Recuperar y defender: intervention, rollback, release, final report. Final presentation on exam date, to be set. Before extending graphics or physics, **validate one full cycle with a simple mission**. Shared resources are checked per scenario; do not assume the crane demo implies engines are ready.

## Notes of use (sec. 19)
Read docs for the versions you pinned. Reserved final test stays out of the public repo. Document licenses of assets. Before delivery verify: URL, teacher access, identity of each model, artifact recovery, and that what you claim matches what you can demonstrate. Brief's illustrations are conceptual, not results. Reference docs: Gymnasium (create env), Three.js manual, SB3 PPO, PyTorch install, MLflow tracking, Git, DVC, Vercel Vite / Functions limits / Daemons.

## Team-guide extras (setup, 4 Nov)
Setup (~20 min): clone, `git switch -c dev/<name>`, push `-u`; venv Python 3.12; install torch CPU then `gymnasium stable-baselines3 mlflow fastapi uvicorn numpy pytest prefect dvc`; one person freezes `requirements.txt`; VS Code interpreter `.venv`; Claude Code extension, open with repo folder; run `/init` then merge with the team `CLAUDE.md` and commit it; VS Code extensions Python, Pylance, ESLint, GitLens, YAML; check `python -c "import gymnasium, stable_baselines3, mlflow; print('ok')"`. Test command: `python -m pytest tests -q`. Proposed `CLAUDE.md` rules (already reflected in SKILL.md): Python sim is authority; no contract change without version bump + `docs/decisiones.md`; one-time milestone rewards, pick/drop same package pays nothing, delivery only at correct station within interaction radius at low speed; `terminated` vs `truncated`; every training logged in MLflow; manifest for each final model; never overwrite a registered model; Git exclusions. Pending team decisions: MLflow persistence location, HTTPS API host, Prefect vs Airflow.
