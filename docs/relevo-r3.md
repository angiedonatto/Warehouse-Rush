# Relevo R3 · Versionado, pipeline y API

Estado al **2026-11-19 13:27 UTC** (verificado contra Render y GitHub).
Responsable: miguel (R3). **PR 1 (#4, https://github.com/angiedonatto/Warehouse-Rush/pull/4): ya está fusionado en `main`**
(2026-11-19 11:37 UTC, con «merge commit» `57e9ff7`). **PR 2 (#5, https://github.com/angiedonatto/Warehouse-Rush/pull/5):**
`dev/miguel-visor` → `main`, la capa `/api/*` (6 commits, 8 archivos); lo revisa y fusiona Angie.

**Dominio definitivo de la web:** `https://warehouse-rush-psi.vercel.app` (ya permitido en `CORS_ORIGINS` de Render, junto con
`experiment-001`).

**Render sirve hoy el commit `8b49d63`** (imagen `ghcr.io/mamezquita/warehouse-rush-api:8b49d63`, rama `dev/miguel-visor`):
la API nueva más la capa `/api/*` del visor, con producción = `m1b-i1-seed1-best`. Anteriores: `e51f075` (PR 1, el
rollback real) y `661fe5a` (primer despliegue real). Evidencia en `docs/resultados/despliegues/` y `docs/resultados/visor/`.

## En una frase

La API nueva (FastAPI, sin torch) **corre en Render (`8b49d63`)** con la capa `/api/*` que usa el visor de la web
(mismas rutas y formatos que el `/api` de Vercel, sesión en la cabecera `X-Sesion`), verificada en producción, con CORS
resuelto para los dos dominios de la web. El PR 1 ya está en `main`; falta que Angie fusione el PR 2 (#5). **La migración de
la web a Render (`docs/api-contrato.md`, sección 9) queda como siguiente paso después de la entrega.**

## Arquitectura acordada

| Capa | Dónde | Estado |
|---|---|---|
| Web (interfaz, Three.js) | Vercel, dominio definitivo `https://warehouse-rush-psi.vercel.app` (lis/Naomi) | En producción; episodios y «Evaluar» todavía por el `/api` de Vercel hasta que migre (después de la entrega) |
| API única de modelos, evaluaciones y episodios | Render Free (`https://warehouse-rush-api.onrender.com`), FastAPI | **Sirve `8b49d63`** (API + capa `/api/*` de `dev/miguel-visor`; producción `m1b-i1-seed1-best`) |
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
| ¿Se probó el rollback real y la recuperación de episodios? | **Rollback real: sí** (2026-11-19): producción → `m1-c3-seed0` → producción en Render, **~25 s** del deploy hook a `/version`; con `m1-c3-seed0` el paso cerrado da 0% en producción (21.62 choques/ep) y al volver, 100%. **Episodios:** se recuperan con `GET /episodios/{id}` mientras el proceso siga vivo; se pierden al redesplegar o dormirse. El rollback está probado en local (flujo y registro, ida y vuelta) y documentado con su efecto medido; falta en Render con el tiempo real de redeploy. Los episodios se recuperan con `GET /episodios/{id}` mientras el proceso siga vivo; **se pierden si Render se duerme (15 min) o se redespliega** (ver `docs/rollback.md`). |

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

**Capa `/api/*` desplegada (2026-11-19, commit `8b49d63`, PR 2)** — `api/_visor.py`, 55 pruebas en `tests/test_visor.py`
(373 en la suite completa) y `docs/api-contrato.md` sección 9. Despliegue con `publicar.sh`: build 3.3 s, push 10.6 s,
**deploy hook → `/version` con el commit nuevo 25.1 s**, precarga lista a los 25.7 s. Verificación en producción
(`docs/resultados/visor/verificacion-produccion.json`, 22 comprobaciones correctas):

| Ruta / caso | Resultado en producción |
|---|---|
| `GET /api/layout` | 2 modelos recomendados (producción primero), catálogo `trendy-27-v1` (27), mapa 0.4.0, 11 KB, sin crear sesión; 0.26 a 0.42 s |
| `GET /api/state` | sin `X-Sesion` crea una sesión (id en la cabecera y en `sesion_id`); con ella devuelve la misma; ~0.3 a 0.5 s |
| `POST /api/reset` con modelo | `m1b-i1-seed1-best`, «N3 · paso (6,14) cerrado», misma sesión, `X-Modelo-Servido` correcto; ~0.4 s |
| `POST /api/step` hasta el final | 111 pasos, éxito, 0 choques (= `/episodios` y la evaluación directa); p50 ~0.3 s, p95 ~0.5 s |
| Visor libre y modo antiguo | «Generar pedido» con inventario compartido (el stock baja y no se repone); modo sin maquillaje funciona |
| `POST /api/evaluate` (10 ep) | `certificado: false`, `trendy-27-v1`; producción 100% en 6.5 a 7.5 s; `m1-c3-seed0` con el paso cerrado 0% en 16 a 18 s |
| **Sesión perdida** | `state`/`step` con un id desconocido → **404 `sesion_no_encontrada`** (texto en formato Vercel); `step` sin cabecera → 400 `falta_sesion` |
| **`reset` la recupera** | con el id perdido crea una sesión nueva (id distinto, misma semilla) y la sesión nueva avanza |
| CORS | `X-Sesion` permitida y expuesta; al desplegar solo pasaba `experiment-001` y `psi.vercel.app` era rechazado: **resuelto** (ver abajo) |

**Hallazgo de CORS: resuelto (2026-11-19, 06:53 UTC).** Al desplegar, el preflight desde
`https://warehouse-rush-psi.vercel.app` respondía 400 «Disallowed CORS origin» porque `CORS_ORIGINS` de Render solo
tenía `experiment-001` (configuración, no la imagen). Tras corregir la variable y dejar la etiqueta de imagen en `8b49d63`,
Render reinició el servicio (`iniciado_en` 06:52:57) y se comprobó, **sin publicar nada**:

| Origen | Preflight `POST /api/step` con `x-sesion` | `GET /api/layout` con `Origin` |
|---|---|---|
| `https://warehouse-rush-experiment-001.vercel.app` | 200, `allow-origin` correcto, `X-Sesion` permitida | 200, `allow-origin` correcto, expone `X-Sesion`, 2 modelos |
| `https://warehouse-rush-psi.vercel.app` | 200, `allow-origin` correcto, `X-Sesion` permitida | 200, `allow-origin` correcto, expone `X-Sesion`, 2 modelos |
| `https://otro.example` (control) | 400 «Disallowed CORS origin» | 200 sin `allow-origin` (el navegador lo bloquea) |

`/version` sigue en `8b49d63`. La etiqueta de imagen por defecto del servicio también quedó en `8b49d63`.

## Qué falta, en orden

1. ~~Dockerfile, `publicar.sh` y despliegue de la imagen real~~: **hecho** (`661fe5a`). La etiqueta de imagen
   por defecto de Render ya está en `8b49d63` (un reinicio manual no vuelve a una imagen vieja).
2. **Commit de la evidencia del despliegue** (`docs/resultados/despliegues/`).
3. ~~Rollback real en Render~~: **hecho** (2026-11-19, tiempos en `docs/rollback.md`).
4. ~~Medir el despertar de Render~~: **hecho** (2026-11-19): 17.6 s la primera petición, 0.38 s después (detalle en
   `docs/rollback.md`). Una sola medición; repetir en otra franja si hace falta.
5. ~~Capa `/api/*` con `ViewerSession`~~: **hecha y desplegada** (`8b49d63`, ver arriba), sin tocar `api/_viewer.py` ni
   nada de Vercel (archivo nuevo `api/_visor.py`). `/episodios` se mantiene como está.
5b. ~~Arreglar `CORS_ORIGINS` en Render~~: **hecho** (2026-11-19 06:53 UTC; los dos dominios pasan el preflight con `X-Sesion`).
5c. **La web migra a Render** (lis y Naomi): `docs/api-contrato.md` sección 9 (dirección base, `X-Sesion`, sesión perdida,
    «Evaluar» no certificado). **Queda como siguiente paso después de la entrega**; hasta entonces la web sigue con su `/api`
    de Vercel (que no se toca) y usa de Render solo `/catalogo`, `/version` y `/monitoreo`.
6. `pipelines/flow.py`: espera configurable en la etapa 8 (un redeploy tarda minutos, no segundos).
7. `docs/decisiones.md`: registrar las decisiones de la tabla de abajo marcadas «por registrar».
8. ~~`docs/api-contrato.md` para lis y Naomi~~: **hecho** (rutas, errores, cabeceras, CORS, evaluación asíncrona, episodios y servidor gratuito).
9. ~~PR 1 (#4)~~: **fusionado en `main`** (2026-11-19 11:37 UTC, merge commit `57e9ff7`). **PR 2 (#5)** (`dev/miguel-visor` → `main`,
   base ya cambiada a `main`): lo revisa y fusiona Angie, con «merge commit», no con «squash» (la trazabilidad de `/version`).
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
| Arranque en frío del contenedor (0.1 CPU, simulado) | 15 s |
| **Despertar real de Render** (1.ª petición a `/version` tras >25 min sin tráfico) / `/health` ya despierto | **17.6 s** (`iniciado_en` 05:40:41, 14 s después de la petición: arranque nuevo confirmado) / **0.38 s** |
| **Redeploy real en Render** (deploy hook → `/version` con el commit nuevo / → precarga ok) | **3.6 s / 21.5 s** (las capas pesadas ya estaban en caché de Render por el prototipo; con una imagen sin capas previas será mayor) |
| Build de la imagen / push a GHCR (capas en caché) | 3.1 s / 20.3 s |
| **Rollback real** (deploy hook → `/version` con el commit nuevo): ida / vuelta | **25.8 s / 25.1 s** (precarga lista a los 26.6 s / 25.8 s) |
| Evaluación certificada de 50 episodios con `m1-c3-seed0` (paso cerrado, falla) / con `m1b-i1-seed1-best` | 75.3 s / 25.2 s en Render |
| Evaluación de 50 episodios | 26.7 s en Render (producción), 27 s en la simulación con 0.1 CPU |
| Episodio completo (`correr`) | 1.3 s en Render, 8.5 KB con gzip |
| **Capa `/api/*` en producción:** `state` / `reset` con modelo / `step` (p50, p95) | 0.3-0.5 s / 0.4 s / 0.3 s, 0.5 s (en local con 0.1 CPU: ~0.1 s por paso; la diferencia es la red) |
| `POST /api/evaluate` 10 episodios en producción (modelo que funciona / que falla) | 6.5-7.5 s / 16-18 s |
| `/version` con una evaluación en curso (simulación 0.1 CPU) | 7.4 s antes de calcular una vez al arrancar → 0.5 s después |
| Rollback de `m1b-i1-seed1-best` a `m1-c3-seed0` | recupera el servicio con el paso abierto (98–100%), pierde el incidente: 0% con el paso cerrado (21.6 choques/ep en `legacy-18`, 85 en `trendy-27`) |

## Riesgos y limitaciones abiertas

- Episodios, evaluaciones y métricas viven en memoria: se pierden al dormirse o redesplegarse Render.
- Render Free: 0.1 CPU (una evaluación larga ocupa la CPU), 512 MB, se duerme a los 15 min y la primera petición
  tarda ~18 s en despertarlo.
- Hasta que la web migre (siguiente paso, después de la entrega) conviven dos servidores (Vercel y Render): la versión servida
  que muestra la web viene de Render, pero los episodios corren en Vercel.
- **CORS:** `CORS_ORIGINS` debe listar cada dominio de la web (hoy `experiment-001` y el definitivo `psi`); un dominio nuevo (por ejemplo un
  preview de Vercel) no funciona hasta agregarlo y guardar (Render reinicia el servicio y se pierden las sesiones en memoria).
- Las sesiones del visor (`/api/*`) también viven en memoria (30 min, máx. 100): se pierden al redesplegar o dormirse; la web
  debe manejar `sesion_no_encontrada` (contrato, 9.6).
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
