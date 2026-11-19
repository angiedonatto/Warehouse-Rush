# Relevo R3 · Versionado, pipeline y API

Estado al **2026-11-18** (noche, hora de Colombia; verificado contra Render y GitHub el 2026-11-19 03:50 UTC).
Responsable: miguel (R3). Rama `dev/miguel` en `d8338bd` (`origin/dev/miguel` en `87669b2`: faltan 3 commits por
subir), **30 commits por delante de `main`** (`b57fa77`), sin commits de `main` pendientes de integrar.

## En una frase

La API nueva (FastAPI, sin torch) está terminada y probada en local y en una simulación de Render, pero **Render
todavía sirve el prototipo de prueba (`6083735`)**: falta construir y desplegar la imagen real, probar el rollback en
producción, migrar la web a la API e integrar todo a `main`.

## Arquitectura acordada

| Capa | Dónde | Estado |
|---|---|---|
| Web (interfaz, Three.js) | Vercel (`warehouse-rush-psi.vercel.app`, lis/Naomi) | En producción; episodios y «Evaluar» todavía por el `/api` de Vercel |
| API única de modelos, evaluaciones y episodios | Render Free (`https://warehouse-rush-api.onrender.com`), FastAPI | **Sirve el prototipo `6083735`**; la versión real está lista para desplegar |
| Registro de experimentos y modelos | MLflow en DagsHub (`mamezquita/Warehouse-Rush.mlflow`) | 94 runs migrados (lis) + run del flujo |
| Pesos | DVC en Cloudflare R2 (entrenamiento) y `models/numpy/` en Git (API) | Hecho |
| Orquestación | Prefect (`pipelines/flow.py`) | Hecho; ejecutado contra DagsHub |

Plan acordado con Angie: **no tocar Vercel hasta que Render esté probado de verdad** → 1) Render en producción y
probado, 2) PR de `dev/miguel` a `main`, 3) validar todo junto, 4) una sola arquitectura (retirar el `/api` de Vercel).

## Respuestas a las preguntas de Angie (al 2026-11-19 03:50 UTC)

| Pregunta | Respuesta |
|---|---|
| ¿Render ya funciona públicamente? | Sí responde (`/health`, `/version`, modelos cargados), pero con el **prototipo** `6083735`. La versión real (portada en `/`, evaluaciones asíncronas, inferencia NumPy verificada) está en `dev/miguel` y falta desplegarla. |
| ¿Se migró toda la simulación? | **No.** La API ya ejecuta episodios con los modelos del catálogo («Cargar en la bodega»). Falta la capa `/api/*` con `ViewerSession` (visor libre de maquillaje, «Generar pedido», mismas rutas que usa la web), que espera la confirmación de Angie y lis para adaptar `api/_viewer.py`. |
| ¿Evaluar ya funciona con suites oficiales? | Sí en local y en la simulación de Render: `POST /evaluaciones` asíncrona, suites fijas, catálogo `legacy-18`, reproduce las evaluaciones congeladas **episodio a episodio**. En producción, después del despliegue. El «Evaluar» rápido de la web (`/api/evaluate`, `trendy-27`, 10 episodios) se mantendrá como diagnóstico **no certificado** en la capa `/api/*`. |
| ¿Se probó el rollback real y la recuperación de episodios? | **No todavía.** El rollback está probado en local (flujo y registro, ida y vuelta) y documentado con su efecto medido; falta en Render con el tiempo real de redeploy. Los episodios se recuperan con `GET /episodios/{id}` mientras el proceso siga vivo; **se pierden si Render se duerme (15 min) o se redespliega** (ver `docs/rollback.md`). |

## Qué está hecho (con commit)

| Pieza | Archivos | Evidencia |
|---|---|---|
| Registro de modelos: catálogo, alias, promover, rollback, SHA-256 | `pipelines/registry.py`, `manifests/aliases.json`, `manifests/catalog.json` | rollback de producción ida y vuelta en pruebas; `tests/test_registry.py` |
| Flujo Prefect de 8 etapas + flujo de rollback | `pipelines/flow.py` | ejecución contra DagsHub: `docs/resultados/flujo/20261118T235015Z-m1b-i1-seed1-best/` |
| MLflow en DagsHub | `.env.example`, decisiones | 94 runs con sus estados; `warehouse-m1`/`warehouse-m1b` v1 con alias `recomendado` |
| Exportación PPO → NumPy verificada | `pipelines/exportar_numpy.py`, `models/numpy/` (20 modelos, 644 KB) | 636 986 pasos comparados con SB3: **0 acciones distintas** |
| API FastAPI | `api/_app.py`, `api/_modelos.py`, `api/_episodios.py` | `tests/test_api.py` (22 pruebas), sin torch |
| — modelos | NumPy, cadena manifiesto → ficha → sha256 del `.npz`; producción precargada | RAM 70 MiB frente a 368 MiB con torch |
| — evaluaciones certificadas | `POST /evaluaciones` (202) + `GET /evaluaciones/trabajos/{id}`; cola de 3, caducan a los 30 min | coincide episodio a episodio con la evaluación congelada |
| — episodios | `/episodios` (crear, paso, correr, ver, cerrar), catálogo `trendy-27-v1`, máx. 200, 30 min | |
| — servicio | `/`, `/health`, `/version`, `/catalogo`, `/monitoreo` (incluye casi empates de NumPy), CORS, errores con una sola forma | |
| `evaluate()` acepta políticas inyectadas (archivo de R2, lis avisada) | `pipelines/evaluate.py` | idéntico byte a byte sin el parámetro |
| Dependencias de la API | `requirements-api.txt` (24, mismas versiones) | `tests/test_requirements_api.py`; venv limpio sin torch |
| Documentación | `docs/decisiones.md`, `docs/rollback.md` | degradación de `m1-c3-seed0` medida en `legacy-18` y `trendy-27` |

**Sin commit todavía:** `api/Dockerfile` y `.dockerignore` (paso 8, esperando aprobación). Probados: imagen de
348 MB sin torch, DVC ni secretos (comprobado aun construyendo desde un árbol con `.env` y credenciales), arranque en
frío en 15 s con 0.1 CPU y 512 MB, evaluación de 50 episodios en 23 s, RAM 70 MiB, y reconstrucción en 2.6 s cuando
solo cambian los manifiestos (rollback).

## Qué falta, en orden

1. **Commit del Dockerfile** (paso 8) y **`api/publicar.sh`** (paso 9): construye desde `git archive` del commit,
   escribe `VERSION.json`, etiqueta con el sha, sube a GHCR (`ghcr.io/mamezquita/warehouse-rush-api`, privado),
   dispara el *deploy hook* y espera a que `/version` muestre el commit (mide el redeploy).
2. **Desplegar la imagen real en Render** (lo hace miguel en el panel: cambiar la imagen del servicio y guardar el
   *deploy hook* en `.env`) y **verificar en producción**: `/`, `/health`, `/version` con el commit real, una
   evaluación certificada asíncrona y episodios.
3. **Rollback real en Render**: producción (`m1b-i1-seed1-best`) → `m1-c3-seed0` → producción, con el flujo
   (`python -m pipelines.flow rollback ...`), midiendo el redeploy; actualizar `docs/rollback.md`.
4. **Medir el despertar de Render** tras 15 min sin tráfico (la web de lis consulta `/version` y lo mantiene
   despierto: hacerlo cuando nadie la tenga abierta).
5. **Capa `/api/*` con `ViewerSession`** (mismas rutas y formatos que usa la web; sesión en la cabecera `X-Sesion`;
   `/episodios` como alias; `/api/evaluate` como diagnóstico no certificado): **espera la confirmación de Angie y lis**
   para adaptar `api/_viewer.py` en vez de retirarlo. Hasta entonces no se toca `_viewer.py` ni nada de Vercel.
6. `pipelines/flow.py`: espera configurable en la etapa 8 (un redeploy tarda minutos, no segundos).
7. `docs/decisiones.md`: registrar las decisiones de la tabla de abajo marcadas «por registrar».
8. **`docs/api-contrato.md`** para lis y Naomi (endpoints, campos y la limitación de memoria).
9. **PR de `dev/miguel` a `main`** (revisa y aprueba Angie) y validación conjunta.
10. Cuando la web ya no lo use: retirar el `/api` de Vercel en un commit aparte (`api/index.py`, `api/_cloud.py`,
    `pipelines/servir.py`, `configs/modelos_servidos.json`, `models/servidos/`) y lo heredado de `warehouse-v1`.

## Decisiones tomadas

| Fecha | Decisión | Registro |
|---|---|---|
| 2026-11-18 | MLflow persistente en DagsHub; credenciales solo en `.env` | `docs/decisiones.md` |
| 2026-11-18 | Orquestador: Prefect; el flujo no promueve (promover y rollback son acciones explícitas) | `docs/decisiones.md` |
| 2026-11-18 | `fastapi==0.150.0` (con 0.162.0 Prefect 3.8.8 no arranca) | `docs/decisiones.md` |
| 2026-11-18 | Manifiestos actualizados a DagsHub por lis (reemplaza «no editar manifiestos») | `docs/decisiones.md` |
| 2026-11-18 | Hugging Face descartado (Spaces Docker exige PRO); API en Render Free desde imagen privada en GHCR | `docs/decisiones.md` |
| 2026-11-18 | **Render es el único servidor de modelos, evaluaciones y episodios** (decisión del equipo) | `docs/decisiones.md` |
| 2026-11-18 | Catálogo: episodios de la web con `trendy-27-v1`; evaluaciones en suites con `legacy-18` (certificado) | `docs/decisiones.md` (lis) y código |
| 2026-11-18 | Inferencia NumPy en la API (sin torch), publicada solo con 0 acciones distintas frente a SB3; `.npz` en Git | por registrar |
| 2026-11-18 | `requirements-api.txt` como subconjunto exacto de `requirements.txt` | por registrar |
| 2026-11-18 | Evaluaciones certificadas asíncronas (cola de 3, caducidad 30 min); `/api/evaluate` = diagnóstico no certificado | por registrar |
| 2026-11-18 | Reutilizar `ViewerSession` como motor único con la capa `/api/*` (pendiente de Angie y lis) | por registrar |
| 2026-11-18 | Plan de Angie: no tocar Vercel hasta probar Render; luego PR, validación conjunta y una sola arquitectura | por registrar |

## Medidas de referencia

| Qué | Valor |
|---|---|
| RAM de la API con torch / con NumPy | 368 MiB / 70 MiB |
| Arranque en frío del contenedor (0.1 CPU, simulado) | 15 s; Render añade su propio despertar (~1 min según su documentación, por medir) |
| Evaluación de 50 episodios | 23 s (simulación de Render) / 26 s (prototipo en Render) |
| Episodio completo (`correr`) | ~1 s, 7–8 KB con gzip |
| Rollback de `m1b-i1-seed1-best` a `m1-c3-seed0` | recupera el servicio con el paso abierto (98–100%), pierde el incidente: 0% con el paso cerrado (21.6 choques/ep en `legacy-18`, 85 en `trendy-27`) |

## Riesgos y limitaciones abiertas

- Episodios, evaluaciones y métricas viven en memoria: se pierden al dormirse o redesplegarse Render.
- Render Free: 0.1 CPU (una evaluación larga ocupa la CPU), 512 MB, se duerme a los 15 min.
- Mientras la web no migre, conviven dos servidores (Vercel y Render): la versión servida que muestra la web viene de
  Render, pero los episodios corren en Vercel.
- Casi empates de NumPy frente a torch: el más ajustado fue `m1-c4-seed1` (margen 3.2× la diferencia numérica, 0
  acciones distintas); `/monitoreo` los cuenta.

## Cómo retomar

```bash
source .venv/bin/activate                     # Python 3.12; uv venv --python 3.12 si falta
python -m pytest tests -q -n 6 --dist loadfile  # suite completa
python -m pytest tests/test_api.py -q           # API (sin DVC ni torch)
uvicorn api._app:app --port 7860 --workers 1    # API en local
python -m pipelines.registry estado             # alias de producción
python -m pipelines.flow ejecutar --run-id m1b-i1-seed1-best --suite suite-m1-v1 --suite suite-m1b-v1
```
