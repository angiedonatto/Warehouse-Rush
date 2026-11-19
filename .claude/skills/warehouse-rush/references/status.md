# Project status vs the brief (2026-11-19, v1.0 released)

Snapshot written right after `v1.0`: tag on `f72f0a2` (deployed commit), `main` at `211acdf` (PR #9, deploy record).
Verify with `git log origin/main`, `git tag -l`, the live URLs and `docs/despliegue.md` before trusting it.

## Deliverables checklist (brief sec. 17 + "how the teacher reviews")

| Deliverable | Status | Where |
|---|---|---|
| Working URL, HTTPS API with CORS | done | web https://warehouse-rush-psi.vercel.app (Vercel, static only); API https://warehouse-rush-api.onrender.com (Render, FastAPI, `/docs`); verified in production with real CORS (5/5 Playwright at v1.0) |
| Reproducible repo + README (install, run, variables, architecture, reproduction) | done (updated in PR #7) | `README.md` (architecture = Render single server, local web against local API, web tests), `.env.example` (`VITE_API_BASE_URL`), `requirements.txt`, `requirements-api.txt`, `web/package-lock.json` |
| Env contract + sheet + three levels | done | `envs/CONTRATO.md` (v10), `docs/ambiente-v0.10.md`, `docs/niveles.md` (N1 `m1o`, N2 `m1`, N3 `m1b`) |
| Baselines, first model, evaluation | done | random 0% / heuristic 100% on every suite (`docs/resultados/eval/lineas-base-*`) |
| >= 4 configs with hypotheses, MLflow runs and states (incl. failed/rejected) | done | `docs/experimentos.md` (pre-registered), 94 runs on DagsHub with `estado` tag |
| Finalists x 3 seeds, comparison, budget | done | `pipelines/compare.py`, `configs/comparaciones/finalistas-m1-v1.yaml` |
| Recoverable models, manifests, artifact refs, SHA-256, normalization | done | `manifests/` (82), DVC on R2, `models/numpy/` (20 API-executable, verified vs SB3), MLflow registry, `manifests/catalog.json` + `aliases.json` |
| Degradation / intervention (N3) | done | `m1-c3-seed0` 98% -> 0% with the gap closed; `m1b-i1` intervention; `m1b-i1-seed1-best` recommended |
| Reserved final test | done (both used, kept out of the repo) | `test-final-m1-v1`, `test-final-m1b-v1` (gitignored; the API refuses `test-final-*`) |
| Orchestrated pipeline | done (Miguel) | Prefect `pipelines/flow.py` (8 stages + rollback flow), run against DagsHub: `docs/resultados/flujo/` |
| Rollback documented and tested | done (Miguel) | `docs/rollback.md`, `tests/test_registry.py`, real rollback on Render (production -> `m1-c3-seed0` -> production, ~25 s) |
| Monitoring minimum | done | API `/monitoreo` (success per scenario, end causes, decision latency, HTTP errors, served model) + «Monitoreo» dialog and served-model chip in the web |
| Web: catalog, identity, load historical model, run an evaluation, compare, modes, deep links | done | load/diagnose any of the 20 executable models; **official evaluation** (`POST /evaluaciones`, progress bar, matches the registered evaluation); comparison of registered evaluations; mode badge; `?modelo=` / `?catalogo=` |
| Release tag | done | `v1.0` + GitHub release (notes with URLs, Render commit, verification, team roles) |
| Asset licenses | done | `docs/licencias.md` |
| **Short report** (decisions, results, limits, contributions) | **missing** | team; Claude can draft it from repo evidence |
| **Final presentation** | **missing** | team; script in requirements.md ("Defense script") |
| **Infra agreed with the teacher** (Render, DagsHub, R2, Prefect) | **to confirm** | team |

## Loose ends (not blocking the delivery)
- **R3 dead code** (point 10 of `docs/relevo-r3.md`): `api/_cloud.py` (about 10 Python tests use it as a session harness), `pipelines/servir.py`, `configs/modelos_servidos.json`, `models/servidos/`. Keep `api/_viewer.py`: Render's `/api/*` layer (`api/_visor.py`) and `pipelines.cli view` use its `ViewerSession` (the contract wrongly lists it for removal).
- **Angie's old Vercel project** (`warehouse-rush-experiment-001`, team `angiedonato2`) is still connected to the GitHub repo: every PR from `Lis-Sanchez-DS` gets a red "Vercel" check ("Git author must have access to the project"). Harmless for `warehouse-rush-psi`; Angie can disconnect it or invite Lis.
- **Render CORS** allows `warehouse-rush-psi.vercel.app` and `warehouse-rush-experiment-001.vercel.app` only: not the alias `warehouse-rush-lis-team2.vercel.app`, nor per-deployment or preview URLs. Previews need `CORS_ORIGIN_REGEX` on Render (Miguel).
- The web shows no build commit of its own (the old Vercel `/api/health` did); the deploy commit is recorded in `docs/despliegue.md` and the release.

## Defense notes
- Open the URL a few minutes before: Render Free sleeps after 15 min (~20 s to wake); the web shows «Despertando el servidor…».
- Official evaluation of 50 episodes: ~25 s with a working model, more than a minute with a failing one (`m1-c3-seed0` on `suite-m1b-v1`). One at a time, queue of 3.
- Live degradation demo: load `m1-c3-seed0` with «Paso (6,14) cerrado» (fails, many collisions) vs `m1b-i1-seed1-best` (solves it).
- Rollback demo: `docs/rollback.md` (alias change + Render redeploy; `/version` and `X-Modelo-Servido` show the change, the web chip updates).
