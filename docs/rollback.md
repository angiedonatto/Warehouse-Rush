# Rollback del modelo servido

Estado: **rollback real probado en Render** (2026-11-19, miguel). El despertar tras 15 min sin tráfico sigue por medir.
(Hugging Face quedó descartado: Spaces Docker exige PRO.)

## Qué significa rollback en este proyecto

- El modelo que sirve la API es `produccion.actual` de `manifests/aliases.json` en el commit desplegado.
- Hoy: `produccion.actual = m1b-i1-seed1-best` (nivel `m1b`, tolera el paso (6,14) cerrado) y
  `produccion.anterior = m1-c3-seed0` (nivel `m1`).
- Rollback = `python -m pipelines.flow rollback --ranura produccion --motivo "..." --api-url <url>`: intercambia
  `actual` y `anterior` (verificando el sha256 del modelo que vuelve), publica `manifests/catalog.json` y verifica
  `/version`. Repetirlo vuelve al estado inicial; el historial de `aliases.json` registra cada cambio.
- Para que la API sirva el cambio hay que hacer commit, publicar una imagen nueva y desplegarla en Render (trazable por commit). Los dos modelos de
  producción ya están precargados en memoria (`api/_modelos.py`), así que tras el redeploy no esperan descarga.

## Antecedente medido: qué se pierde al volver a `m1-c3-seed0`

El rollback **recupera el servicio** (un modelo verificado que completa la misión en el mapa normal), pero
**pierde el escenario del incidente N3**: `m1-c3-seed0` no sabe rodear el paso cerrado.

| Modelo | Escenario | Fuente | Éxito | Choques/ep | Causa de fin |
|---|---|---|---:|---:|---|
| `m1-c3-seed0` | paso abierto (`suite-m1-v1`) | `docs/resultados/eval/incidente-m1-c3-seed0/` (lis, 2026-11-15) | 98% (49/50) | 0.0 | 49 éxito, 1 límite de tiempo |
| `m1-c3-seed0` | paso cerrado (`suite-m1b-v1`) | misma evaluación | **0%** (0/50) | 21.6 | 45 límite de tiempo, 5 batería agotada |
| `m1b-i1-seed1-best` | paso abierto / cerrado | `manifests/m1b-i1-seed1-best.json` | 100% / 100% | 0.0 / 0.0 | éxito |

Comprobación con la API (`api/_episodios.py`, 2026-11-18, todavía con el catálogo `legacy-18`), semilla 10000, determinista:

- `m1-c3-seed0` con el paso cerrado: **no completa**, `battery_depleted`, **210 choques**, 228 pasos.
- `m1-c3-seed0` con el paso abierto: completa en 82 pasos.
- `m1b-i1-seed1-best` con el paso cerrado: completa en 107 pasos, 0 choques.

Los tres coinciden episodio a episodio con las evaluaciones congeladas de la suite (misma semilla, mismo resultado),
lo que muestra que la API ejecuta la misma simulación que el pipeline de evaluación.

### Con el catálogo de la web (`trendy-27-v1`)

Los episodios de la web usan el catálogo operativo `trendy-27-v1` (decisión de lis, 2026-11-18); las evaluaciones
certificadas siguen con `legacy-18`. El diagnóstico de lis (`docs/resultados/eval/catalogo-trendy-27/resultados.json`)
no incluía el caso del rollback: `m1-c3-seed0` con el paso cerrado. Medido el 2026-11-18
(`docs/resultados/eval/catalogo-trendy-27/medir_rollback.py` → `rollback_m1-c3-seed0.json`, 50 episodios, semillas
10000–10049, determinista, sha256 del modelo verificado):

| `m1-c3-seed0` | Catálogo | Éxito | Choques/ep | Causas de fin |
|---|---|---:|---:|---|
| paso cerrado | `trendy-27-v1` | **0%** (0/50) | **85.0** | 30 límite de tiempo, 20 batería agotada |
| paso abierto | `trendy-27-v1` | 100% (50/50), 82.3 pasos | 0.0 | 50 éxito |
| paso cerrado | `legacy-18` (control) | 0% | 21.6 | 45 límite de tiempo, 5 batería agotada |
| paso abierto | `legacy-18` (control) | 98%, 86.8 pasos | 0.0 | 49 éxito, 1 límite de tiempo |

El control reproduce la evaluación congelada, así que la medición es comparable. Con el catálogo de la web el
rollback a `m1-c3-seed0` **también pierde el escenario del incidente**, y choca más (85 frente a 21.6 choques por
episodio); con el paso abierto completa todo. Semilla 10000 con `trendy-27-v1`: paso cerrado → límite de tiempo, 400
pasos, 0 choques; paso abierto → éxito en 88 pasos.

**Consecuencia operativa:** el rollback a `m1-c3-seed0` es aceptable mientras el paso (6,14) esté abierto. Si el
incidente sigue activo, volver a `m1-c3-seed0` deja la operación sin un modelo que funcione en ese escenario; en ese
caso conviene mantener `m1b-i1-seed1-best` o servir la heurística como referencia mientras se corrige.

## Qué se pierde y qué no al dormirse o redesplegarse Render

La API corre en un solo proceso de Render Free, que **se duerme tras 15 min sin tráfico** y se reinicia en cada
redeploy (también en un rollback). Lo que vive en memoria de ese proceso se pierde; lo que viene de la imagen no:

| Qué | Dónde vive | ¿Se pierde al dormirse o redesplegarse? |
|---|---|---|
| Episodios (`/episodios/{id}`) | memoria del proceso (caducan además a los 30 min sin uso; máx. 200) | **Sí**: la web debe crear uno nuevo (el GET responde 404 `episodio_no_encontrado`) |
| Evaluaciones en curso o terminadas (`/evaluaciones/trabajos/{id}`) | memoria del proceso (las terminadas caducan a los 30 min sin consultarse) | **Sí**: hay que volver a lanzarlas |
| Métricas de `/monitoreo` | memoria del proceso | **Sí**: los contadores vuelven a cero |
| Modelos (`models/numpy/`), manifiestos, catálogo y alias (`manifests/`) | dentro de la imagen (Git, commit en `/version`) | **No** |
| Evaluaciones congeladas (`GET /evaluaciones/{run_id}`) | dentro de la imagen (`docs/resultados/eval/`) | **No** |

Por eso la prueba de rollback verifica el modelo servido con `/version` (estado de la imagen) y no espera conservar
episodios abiertos a través del redeploy.

## Prueba de rollback real en Render (2026-11-19)

Producción (`m1b-i1-seed1-best`) → `m1-c3-seed0` → producción, en el servicio real
`https://warehouse-rush-api.onrender.com`, con el flujo (`pipelines.flow rollback`) y `api/publicar.sh`. Evidencia:
`docs/resultados/flujo/20261119T050830Z-rollback-produccion/` (ida), `…/20261119T051223Z-rollback-produccion/`
(vuelta), `docs/resultados/despliegues/20261119T051036Z-20deead.json` (ida) y
`…20261119T051327Z-e51f075.json` (vuelta).

| Paso | Ida (a `m1-c3-seed0`) | Vuelta (a `m1b-i1-seed1-best`) |
|---|---|---|
| `pipelines.flow rollback` (alias + catálogo, sha256 verificado) | 0.5 s + 6.8 s | 0.5 s + 2.9 s |
| Commit | `781abd5` (alias) y `20deead` (arreglo de una prueba, ver abajo) | `e51f075` |
| `publicar.sh`: build / push a GHCR | 3.7 s / 6.0 s | 2.7 s / 6.2 s |
| **Deploy hook → `/version` muestra el commit nuevo (tiempo de redeploy)** | **25.8 s** | **25.1 s** |
| Deploy hook → precarga de producción lista | 26.6 s | 25.8 s |
| `/version` tras el cambio | `m1-c3-seed0`, sha `b6034b33…`, catálogo al día, aliases v2 | `m1b-i1-seed1-best`, sha `46984e97…`, catálogo al día, aliases v3 |
| `X-Modelo-Servido` | `m1-c3-seed0@b6034b3396a6` (antes `m1b-i1-seed1-best@46984e97b032`) | `m1b-i1-seed1-best@46984e97b032` |

**El tiempo de rollback que se reporta es ~25 s** (deploy hook → `/version`); con el flujo, el build y el push, de
la orden al servicio cambiado pasan unos 40 a 45 s (sin contar el commit y el push manuales). Es corto porque solo
cambian los manifiestos: las capas de dependencias y código salen de caché (reconstrucción de 2.7 a 3.7 s). Una
imagen sin capas previas en Render tardaría más.

**Qué se observó en producción con cada modelo** (`suite-m1b-v1`, certificada, `legacy-18`, paso cerrado):

| Modelo servido | Éxito | Choques/ep | Tiempo de la evaluación en Render |
|---|---:|---:|---:|
| `m1-c3-seed0` (rollback) | **0%** (45 límite de tiempo, 5 batería agotada) | 21.62 | 75.3 s |
| `m1b-i1-seed1-best` (producción) | **100%**, 106.92 pasos | 0.0 | 25.2 s |

Con el rollback, un episodio con el paso cerrado (`trendy-27-v1`, semilla 10000) termina por límite de tiempo y
`correr` tarda 4.0 s (frente a 1.3 s con el modelo de producción). Es lo anotado como antecedente: el rollback
recupera el servicio pero **pierde el escenario del incidente N3**; las cifras en producción coinciden con la
evaluación congelada (0% y 21.62 choques/ep).

**Hallazgo de la prueba:** `test_rollback_pierde_el_escenario_del_incidente` suponía que el modelo servido (sin
`run_id`) era `m1b-i1-seed1-best`, así que con el rollback real fallaba y `publicar.sh` (que corre las pruebas antes
de construir) se detuvo, como debe. La prueba usa ahora `run_id` explícito y comprueba aparte que sin `run_id` se
usa el modelo servido (`20deead`).

## Pendiente

- Tiempo de despertar de Render Free tras 15 min sin tráfico: la primera medición (2026-11-18) no sirvió porque el
  servicio no llegó a dormirse (mismo proceso antes y después); repetirla sin tráfico de nadie.
