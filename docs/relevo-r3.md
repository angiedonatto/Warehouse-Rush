# Relevo R3 · Versionado, pipeline y API

Estado al **2026-11-19 05:00 UTC** (verificado contra Render y GitHub tras el primer despliegue real).
Responsable: miguel (R3). Rama `dev/miguel` en `661fe5a`, igual que `origin/dev/miguel`; **más de 30 commits por delante
de `main`** (`b57fa77`), sin commits de `main` pendientes de integrar.

**Render sirve hoy el commit `661fe5a`** (la versión real, imagen `ghcr.io/mamezquita/warehouse-rush-api:661fe5a`),
desplegado el 2026-11-19 05:00 UTC con `api/publicar.sh`. Evidencia: `docs/resultados/despliegues/20261119T050007Z-661fe5a.json`.

## En una frase

La API nueva (FastAPI, sin torch) **ya corre en Render (`661fe5a`)** y está verificada en producción (portada,
`/version` con catálogo al día, evaluación certificada asíncrona y episodios). Falta probar el rollback real,
medir el despertar, migrar la web a la API (capa `/api/*`) e integrar todo a `main`.

## Arquitectura acordada

| Capa | Dónde | Estado |
|---|---|---|
| Web (interfaz, Three.js) | Vercel (`warehouse-rush-psi.vercel.app`, lis/Naomi) | En producción; episodios y «Evaluar» todavía por el `/api` de Vercel |
| API única de modelos, evaluaciones y episodios | Render Free (`https://warehouse-rush-api.onrender.com`), FastAPI | **Sirve la versión real `661fe5a`** (desde 2026-11-19 05:00 UTC) |
| Registro de experimentos y modelos | MLflow en DagsHub (`mamezquita/Warehouse-Rush.mlflow`) | 94 runs migrados (lis) + run del flujo |
| Pesos | DVC en Cloudflare R2 (entrenamiento) y `models/numpy/` en Git (API) | Hecho |
| Orquestación | Prefect (`pipelines/flow.py`) | Hecho; ejecutado contra DagsHub |

Plan acordado con Angie: **no tocar Vercel hasta que Render esté probado de verdad** → 1) Render en producción y
probado, 2) PR de `dev/miguel` a `main`, 3) validar todo junto, 4) una sola arquitectura (retirar el `/api` de Vercel).

## Respuestas a las preguntas de Angie (al 2026-11-19 03:50 UTC)

| Pregunta | Respuesta |
|---|---|
| ¿Render ya funciona públicamente? | **Sí, con la versión real `661fe5a`**: portada en `/`, `/version` con el commit y el catálogo al día, modelos de producción cargados con inferencia NumPy, evaluaciones asíncronas y episodios (medidas abajo). |
| ¿Se migró toda la simulación? | **No.** La API ya ejecuta episodios con los modelos del catálogo («Cargar en la bodega»). Falta la capa `/api/*` con `ViewerSession` (visor libre de maquillaje, «Generar pedido», mismas rutas que usa la web), que espera la confirmación de Angie y lis para adaptar `api/_viewer.py`. |
| ¿Evaluar ya funciona con suites oficiales? | **Sí, también en producción**: `POST /evaluaciones` asíncrona, suite `suite-m1b-v1`, catálogo `legacy-18`, 100% y 106.92 pasos, 0 choques (igual que la evaluación congelada), 26.7 s en el servidor. El «Evaluar» rápido de la web (`/api/evaluate`, `trendy-27`, 10 episodios) se mantendrá como diagnóstico **no certificado** en la capa `/api/*`. |
| ¿Se probó el rollback real y la recuperación de episodios? | **No todavía** (es lo siguiente, con aviso previo). El rollback está probado en local (flujo y registro, ida y vuelta) y documentado con su efecto medido; falta en Render con el tiempo real de redeploy. Los episodios se recuperan con `GET /episodios/{id}` mientras el proceso siga vivo; **se pierden si Render se duerme (15 min) o se redespliega** (ver `docs/rollback.md`). |

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

**Despliegue:** `api/Dockerfile`, `.dockerignore` y `api/publicar.sh` (en `dev/miguel`). Imagen de 348 MB sin torch,
DVC ni secretos (comprobado aun construyendo desde un árbol con `.env` y credenciales); reconstrucción en 2.6 s cuando
solo cambian los manifiestos. `publicar.sh` nunca imprime el deploy hook ni los tokens.

**Primer despliegue real (2026-11-19, commit `661fe5a`)**, verificado en producción:

| Comprobación | Resultado |
|---|---|
| `GET /` | portada con la API, el modelo servido (`m1b-i1-seed1-best`), el commit y los 5 enlaces |
| `/version` | commit `661fe5a`, `warehouse-v10`, catálogo **al día**, aliases v1, precarga ok, 2 modelos cargados (NumPy); cabeceras `X-Git-Commit` y `X-Modelo-Servido` correctas |
| Evaluación certificada asíncrona | `suite-m1b-v1`: 202 → progreso 1, 8, 14 … 50 → terminada; **100%, 106.92 pasos, 0 choques**, 26.7 s en el servidor (29.1 s desde el POST) |
| Episodio (`trendy-27-v1`, paso cerrado, semilla 10000) | `correr` en 1.3 s (8.5 KB con gzip); completa en 111 pasos, 0 choques |
| `/monitoreo` | 5 457 decisiones, 0 casi empates, p95 0.14 ms por decisión |

## Qué falta, en orden

1. ~~Dockerfile, `publicar.sh` y despliegue de la imagen real~~: **hecho** (`661fe5a`). Pendiente menor: en Render,
   *Settings → Image*, cambiar la etiqueta por defecto a la nueva para que un reinicio manual no vuelva al prototipo.
2. **Commit de la evidencia del despliegue** (`docs/resultados/despliegues/`).
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
| **Redeploy real en Render** (deploy hook → `/version` con el commit nuevo / → precarga ok) | **3.6 s / 21.5 s** (las capas pesadas ya estaban en caché de Render por el prototipo; con una imagen sin capas previas será mayor) |
| Build de la imagen / push a GHCR (capas en caché) | 3.1 s / 20.3 s |
| Evaluación de 50 episodios | 26.7 s en Render (producción), 27 s en la simulación con 0.1 CPU |
| Episodio completo (`correr`) | 1.3 s en Render, 8.5 KB con gzip |
| `/version` con una evaluación en curso (simulación 0.1 CPU) | 7.4 s antes de calcular una vez al arrancar → 0.5 s después |
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
