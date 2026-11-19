# Contrato de la API de Warehouse Rush (para la web)

Esta es la guía de lo que la web puede pedirle a la API y de lo que va a recibir. Está sacada del código
(`api/_app.py`, `api/_episodios.py`, `api/_modelos.py`) y de las pruebas (`tests/test_api.py`); los ejemplos son
respuestas reales, recortadas. Si algo de aquí no coincide con la API, manda el código: la lista completa y
siempre está en `GET /docs` (documentación interactiva de FastAPI).

- **Dirección en producción:** `https://warehouse-rush-api.onrender.com`
- **Formato:** todo es JSON. Las peticiones con cuerpo llevan `Content-Type: application/json`.
- **Quién manda:** la simulación corre en la API (Python). La web solo dibuja lo que la API devuelve.
- **Qué cubre:** modelos, evaluaciones oficiales y episodios con los modelos del catálogo (secciones 2 a 8) y,
  **además, la capa `/api/*`** (sección 9): las mismas rutas y formatos que hoy usa la web contra Vercel
  (`/api/layout`, `/api/state`, `/api/reset`, `/api/step`, `/api/evaluate`), para que la web cambie solo la dirección
  base y la forma de guardar la sesión. Incluye el **visor libre de pedidos** (la casilla «Pedidos de maquillaje»).

## 1. Lo básico que conviene saber primero

| Tema | Qué esperar |
|---|---|
| Errores | Siempre con la misma forma (sección 3). Mira el campo `codigo`, no el texto. |
| Modelo servido | Cada respuesta trae la cabecera `X-Modelo-Servido` (sección 4). |
| Evaluaciones | Son asíncronas: pides, recibes un número y consultas hasta que termine (sección 6). |
| Episodios | Viven en la memoria del servidor 30 minutos y **se pierden** si el servidor se redespliega o se duerme (sección 7). |
| Servidor gratuito | Se duerme tras 15 min sin uso y puede tardar en despertar; y va más lento mientras evalúa (sección 8). |
| Cookies | No se usan. Haz las peticiones con `credentials: 'omit'`. El episodio se identifica por su `episodio_id` y la sesión del visor por la cabecera `X-Sesion` (sección 9). |

## 2. Rutas

Resumen:

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/` | Portada: qué API es, qué modelo sirve y enlaces |
| GET | `/health` | ¿Está viva y con los modelos cargados? |
| GET | `/version` | Qué modelo y qué commit sirve, y si el catálogo está al día |
| GET | `/catalogo` | Lista de modelos (filtrable) |
| GET | `/catalogo/{run_id}` | Ficha de un modelo |
| POST | `/modelos/{run_id}/cargar` | Deja un modelo listo en memoria |
| GET | `/evaluaciones/{run_id}` | Evaluaciones ya hechas de un modelo (no ejecuta nada) |
| POST | `/evaluaciones` | **Lanza** una evaluación oficial (asíncrona) |
| GET | `/evaluaciones/trabajos/{evaluacion_id}` | Estado y resultado de esa evaluación |
| POST | `/episodios` | Crea un episodio |
| GET | `/episodios/{episodio_id}` | Estado actual del episodio |
| POST | `/episodios/{episodio_id}/paso` | Avanza un paso |
| POST | `/episodios/{episodio_id}/correr` | Corre hasta el final y devuelve toda la trayectoria |
| DELETE | `/episodios/{episodio_id}` | Cierra el episodio |
| GET | `/layout?nivel=` | Mapa y productos para dibujar la bodega |
| GET | `/monitoreo` | Estadísticas de uso, éxito y latencia |

### GET `/`

No recibe nada. Devuelve el nombre de la API, el modelo servido, el commit y enlaces relativos.

```json
{
  "api": "Warehouse Rush API",
  "environment_version": "warehouse-v10",
  "modelo_servido": {"run_id": "m1b-i1-seed1-best", "model_sha256": "46984e97…", "level_id": "m1b", "anterior": "m1-c3-seed0"},
  "git_commit": "e51f075…",
  "enlaces": {"docs": "/docs", "health": "/health", "version": "/version", "catalogo": "/catalogo", "monitoreo": "/monitoreo"}
}
```

`anterior` es el modelo al que volvería un rollback.

### GET `/health`

Responde 200 mientras el servidor esté vivo. `status` es `ok`, o `degradado` si los modelos de producción no
pudieron cargarse. `precarga` es `en curso`, `ok`, `parcial` o `fallido`: al despertar, el servidor tarda unos
segundos en dejar listos los modelos, así que conviene esperar a `ok` antes de crear episodios.

```json
{"status": "ok", "precarga": "ok", "episodios": {"episodios": 0, "activos": 0, "maximo": 200, "ttl_s": 1800}, "iniciado_en": "2026-11-19T05:23:27Z"}
```

`iniciado_en` cambia cada vez que el servidor arranca de nuevo (redeploy o despertar): si cambia, los episodios
anteriores ya no existen.

### GET `/version`

Qué se está sirviendo exactamente. Es lo que la web debe mostrar como «modelo servido».

```json
{
  "run_id": "m1b-i1-seed1-best",
  "model_sha256": "46984e97b032920c…",
  "environment_version": "warehouse-v10",
  "level_id": "m1b",
  "anterior": "m1-c3-seed0",
  "git_commit": "e51f075…",
  "environment_sheet_version": "0.10.0",
  "catalogo": {"contenido_sha256": "3825e77a…", "aliases_version": 3, "al_dia": true},
  "modelos_cargados": [{"run_id": "m1b-i1-seed1-best", "inferencia": "numpy", "fijo": true, "decisiones": 0, "casi_empates": 0}],
  "precarga": {"estado": "ok", "segundos": 0.5},
  "iniciado_en": "2026-11-19T05:23:27Z"
}
```

`modelos_cargados` trae más campos (`npz_sha256`, `usos`, …); los de arriba son los útiles para mostrar.

### GET `/catalogo`

Parámetros opcionales en la URL: `nivel` (`m1`, `m1b`, `m1o`) y `estado` (`candidato`, `recomendado`, `rechazado`,
`fallido`, `interrumpido`).

Devuelve `{ "modelos": [...], "niveles": {...}, "produccion": {...}, ... }`. En `produccion` está `actual` y
`anterior`; en `niveles`, el recomendado de cada nivel. Cada modelo trae, entre otros: `run_id`, `level_id`,
`estado`, `alias`, `environment_version`, `evaluable_con_api` (si la API puede ejecutarlo), `seed`,
`parent_run_id`, `budget_steps`, `evaluation_suite_id`, `evaluacion` (éxito, choques, pasos), `test_final`,
`decision_reason` y `mlflow_run_id`.

```json
{"run_id": "m1-c3-seed0", "level_id": "m1", "estado": "recomendado", "alias": ["recomendado:m1", "anterior:produccion"],
 "evaluable_con_api": true, "evaluacion": {"suite": "suite-m1-v1", "episodios": 50, "ppo": {"success_rate": 0.98, "mean_steps": 93.04}}}
```

Solo los modelos con `evaluable_con_api: true` y versión NumPy se pueden usar en episodios y evaluaciones; los
de versiones anteriores del ambiente aparecen en el catálogo pero la API responde 409 si se piden.

### GET `/catalogo/{run_id}`

Devuelve `{ "modelo": {...}, "manifiesto": {...} }`: la entrada del catálogo y el manifiesto completo (hashes,
procedencia, configuración). Si el modelo no existe: 404 `modelo_no_encontrado`.

### POST `/modelos/{run_id}/cargar`

No lleva cuerpo. Verifica el modelo y lo deja en memoria. No es obligatorio: crear un episodio o una evaluación
ya lo carga. Devuelve su resumen (`run_id`, `model_sha256`, `inferencia: "numpy"`, `fijo`, `usos`, …).
Errores posibles: 404 `modelo_no_encontrado`, 409 `modelo_incompatible` o `sin_version_numpy`, 500 `integridad`
(el archivo no coincide con su huella: no se carga).

### GET `/evaluaciones/{run_id}`

Devuelve las evaluaciones **ya hechas** y guardadas de ese modelo; no ejecuta nada y responde al instante.
Con `?episodios=true` incluye el detalle por episodio.

```json
{"run_id": "m1-c3-seed0", "evaluation_suite_id": "suite-m1-v1", "manifiesto": {…}, "test_final": {…}, "results_uri": "docs/resultados/eval/m1-c3-seed0/evaluation.json", "resultados": {"summary": […]}}
```

### POST `/evaluaciones` y GET `/evaluaciones/trabajos/{evaluacion_id}`

Lanzan y consultan una evaluación oficial. Se explican en la sección 6.

### POST `/episodios`

Crea un episodio nuevo y devuelve su estado inicial (código **201**).

Cuerpo (todos los campos son opcionales):

| Campo | Valores | Por defecto | Qué hace |
|---|---|---|---|
| `politica` | `ppo`, `heuristic`, `random`, `manual` | `ppo` | Quién decide cada paso |
| `run_id` | un modelo del catálogo | el modelo servido | Solo con `ppo` |
| `nivel` | `m1`, `m1b`, `m1o` | el del modelo; `m1` si no es `ppo` | Mapa y nivel |
| `bloqueado` | `true` / `false` | el del nivel (`m1b`: cerrado) | Paso (6,14) cerrado (solo el mapa con muro) |
| `seed` | entero de 0 a 4 294 967 295 | `10000` | Fija el pedido: la misma semilla da el mismo pedido |

La política determina el **modo** que declara la respuesta, para que la web lo rotule:

| `politica` | `modo` |
|---|---|
| `ppo` | `evaluacion` |
| `heuristic` | `referencia` |
| `random` | `aleatoria` |
| `manual` | `manual` |

Respuesta (recortada; los campos de `state`, `info`, `trail` y `events` son los de siempre del simulador):

```json
{
  "episodio_id": "n8bYlvrfegXWEgfj", "modo": "evaluacion", "politica": "ppo",
  "run_id": "m1b-i1-seed1-best", "model_sha256": "46984e97…", "nivel": "m1b", "bloqueado": true,
  "escenario": "m1b/cerrado", "seed": 10000, "environment_version": "warehouse-v10",
  "catalog_version": "trendy-27-v1", "layout_path": "configs/layout_v0.4.json",
  "done": false, "terminated": false, "truncated": false,
  "last_action": null, "last_reward": 0.0, "observation": [/* 27 números */],
  "state": {"x": 3, "y": 16, "theta": 0, "bateria": 180, "etapa": "recoger", "objetivo": "E06", "tiempo": 0,
            "entregas": 0, "colisiones": 0, "pasillo_bloqueado": true, "inventory": {…}, "order": {…},
            "capacity": 3, "lift": {…}, "cargo_lines": []},
  "info": {"success": false, "end_reason": null, "steps": 0, "collisions": 0, "deliveries": 0, "layout_sha256": "a007d66b…"},
  "trail": [[3, 16]], "events": [{"step": 0, "kind": "reset", "text": "Pedido generado. Robot en BASE."}],
  "creado_en": "…", "caduca_en_s": 1800
}
```

Los episodios usan el catálogo de productos de la web (`trendy-27-v1`, 27 productos). Cada episodio es un pedido de
3 productos distintos, de 1 unidad cada uno.

### GET `/episodios/{episodio_id}`

Devuelve el mismo formato que la creación, con el estado actual. Sirve para recuperar el episodio al recargar la
página (guarda el `episodio_id` en la URL o en `localStorage`). Si ya no existe: 404 `episodio_no_encontrado`.

### POST `/episodios/{episodio_id}/paso`

Avanza **un** paso y devuelve el episodio actualizado.

- Con `politica: "manual"`, el cuerpo es obligatorio: `{"accion": 0}` a `{"accion": 7}`.
- Con las demás políticas **no** se envía acción (el cuerpo va vacío o se omite); la política decide sola.

Acciones: `0` AVANZAR, `1` GIRAR_IZQUIERDA, `2` GIRAR_DERECHA, `3` FRENAR, `4` CARGAR, `5` DESCARGAR, `6` SUBIR,
`7` BAJAR. Si el episodio ya terminó: 409 `episodio_terminado`.

### POST `/episodios/{episodio_id}/correr`

Corre el episodio hasta el final y devuelve **toda la trayectoria** para que la web la anime en su navegador. Es
mucho más eficiente que pedir un paso por petición (con el servidor gratuito, cada petición tiene su tiempo).
Cuerpo opcional: `{"max_pasos": 50}` (de 1 a 400) para correr solo una parte. No aplica al modo manual (400).

```json
{
  "pasos": 111,
  "trayectoria": [{"paso": 1, "accion": {"code": 0, "name": "AVANZAR"}, "recompensa": 0.184, "estado": {"x": 3, "y": 15, "…": "…"}}],
  "final": { /* el episodio completo, con done, info.success, info.end_reason */ }
}
```

La trayectoria pesa unos 200 KB sin comprimir y unos 8 KB con gzip (el servidor comprime solo). Cada cuadro trae
el estado sin el inventario completo; este va en `final.state`.

### DELETE `/episodios/{episodio_id}`

Cierra el episodio y libera su lugar. Devuelve `{"episodio_id": "…", "cerrado": true}`.

### GET `/layout?nivel=m1`

Parámetro `nivel`: `m1` (por defecto), `m1b` o `m1o`. Devuelve lo necesario para dibujar la bodega con el mismo
catálogo que usan los episodios.

```json
{"nivel": "m1b", "layout_path": "configs/layout_v0.4.json", "layout": {…}, "layout_sha256": "a007d66b…",
 "bloqueado_por_defecto": true, "catalog": [{"sku": "…", "name": "…", "category": "…", "rack": "E01", "level": "E01-L1", "height_m": 0.99, "initial_stock": 5}],
 "catalog_version": "trendy-27-v1", "catalogo_evaluaciones": "legacy-18", "environment_version": "warehouse-v10"}
```

### GET `/monitoreo`

Estadísticas desde que el servidor arrancó (se reinician con cada arranque): modelo servido, éxito por modelo y
escenario con las causas de fin, latencia de cada decisión (p50, p95, máximo), peticiones y errores por ruta, la
cola de evaluaciones, los episodios abiertos y los modelos en memoria (con el conteo de decisiones y de «casi
empates»).

```json
{"servido": {"run_id": "m1b-i1-seed1-best", "…": "…"}, "evaluaciones": {"por_estado": {"terminada": 1}, "cola_max": 3, "ttl_s": 1800},
 "exito_por_escenario": [{"quien": "heuristic", "escenario": "m1/abierto", "episodios": 10, "exitos": 10, "tasa_exito": 1.0, "causas": {"success": 10}}],
 "latencia_decision": {"m1b-i1-seed1-best": {"n": 111, "p50_ms": 0.019, "p95_ms": 0.064, "max_ms": 0.154}},
 "episodios": {"episodios": 1, "activos": 1, "maximo": 200, "ttl_s": 1800}}
```

## 3. Formato de errores

Todo error, de cualquier ruta, tiene la misma forma:

```json
{"error": {"codigo": "episodio_no_encontrado",
           "mensaje": "El episodio no existe o caducó (30 min sin uso); crea uno nuevo",
           "detalle": {"episodio_id": "xx"}}}
```

- `codigo`: identificador estable. **Usa este** para decidir qué hacer.
- `mensaje`: texto en español pensado para mostrar al usuario.
- `detalle`: datos adicionales (puede estar vacío `{}`).

| Estado | `codigo` | Cuándo |
|---|---|---|
| 400 | `parametro_invalido` | Un valor no es válido (por ejemplo `run_id` con una política que no es `ppo`, `correr` en modo manual, acción en un episodio no manual) |
| 404 | `modelo_no_encontrado` | El modelo no existe en el catálogo |
| 404 | `episodio_no_encontrado` | El episodio no existe o caducó |
| 404 | `evaluacion_no_encontrada` | La evaluación no existe o caducó (30 min después de terminar) |
| 404 | `suite_no_disponible` | La suite no existe o es reservada |
| 404 | `ruta_no_encontrada` | La ruta no existe |
| 405 | `metodo_no_permitido` | Método HTTP equivocado para esa ruta |
| 409 | `modelo_incompatible` | El modelo es de otra versión del ambiente, o su mapa no corresponde al nivel o la suite pedidos |
| 409 | `sin_version_numpy` | El modelo no tiene versión ejecutable en la API |
| 409 | `episodio_terminado` | Se pidió avanzar un episodio que ya terminó |
| 422 | `parametro_invalido` | El cuerpo no cumple el formato (ver abajo) |
| 429 | `demasiados_episodios` | Hay 200 episodios activos |
| 429 | `cola_llena` | Ya hay 3 evaluaciones esperando |
| 500 | `integridad` | La huella de un archivo del modelo no coincide: el modelo no se carga |
| 500 | `evaluacion_fallida`, `sin_produccion`, `error_interno` | Fallos internos |

**Los cuerpos son estrictos:** `"seed": "5"` (texto en lugar de número) o un campo que no existe devuelven 422.
En ese caso, `detalle.errores` es una lista de `{"campo": "seed", "problema": "…"}`.

## 4. Cabeceras `X-Modelo-Servido` y `X-Git-Commit`

Todas las respuestas, también las de error, las traen:

| Cabecera | Ejemplo | Significado |
|---|---|---|
| `X-Modelo-Servido` | `m1b-i1-seed1-best@46984e97b032` | `run_id` del modelo de producción y los primeros 12 caracteres de su huella (`sha256`) |
| `X-Git-Commit` | `e51f075acbab…` | Commit del código desplegado |

Para que el navegador pueda leerlas desde otro dominio, la API las declara como visibles (sección 5). Úsalas para
avisar cuando cambia el modelo servido (por ejemplo, tras un rollback): si el valor de `X-Modelo-Servido` cambia
entre dos respuestas, mostrar el aviso y volver a pedir `/version`. Si no se puede determinar el modelo, el valor
es `desconocido`.

## 5. CORS (llamadas desde el navegador)

- Solo los dominios listados en la variable `CORS_ORIGINS` del servidor pueden llamar a la API desde un
  navegador. Hoy: `https://warehouse-rush-experiment-001.vercel.app` y `https://warehouse-rush-psi.vercel.app`.
  **Un dominio nuevo (por ejemplo, un preview de Vercel) no funciona hasta que se agregue** a esa variable.
- Métodos permitidos: `GET`, `POST`, `DELETE`. Cabeceras de petición permitidas: `Content-Type` y `X-Sesion`.
- **Sin credenciales:** no se envían ni se aceptan cookies. En `fetch`, usa `credentials: 'omit'`.
- Cabeceras visibles para el navegador: `X-Modelo-Servido`, `X-Git-Commit` y `X-Sesion`.
- El navegador guarda 10 minutos la respuesta de las consultas previas (`OPTIONS`).
- Si un dominio no está permitido, el servidor responde pero **sin** la cabecera de permiso, y el navegador bloquea
  la respuesta (en la consola aparece un error de CORS, no uno de la API).

## 6. Evaluaciones asíncronas (cómo funcionan)

Una evaluación oficial corre un modelo en una suite fija de episodios (semillas fijas, política determinista,
catálogo `legacy-18`). Con 50 episodios tarda unos 25 s si el modelo funciona y más de un minuto si falla, así que
**no se espera en la misma petición**: se pide, se recibe un número y se pregunta hasta que termine.

**1. Lanzar:** `POST /evaluaciones`

| Campo | Valores | Por defecto |
|---|---|---|
| `suite_id` (obligatorio) | una suite oficial, p. ej. `suite-m1-v1`, `suite-m1b-v1`, `suite-m1o-v1`, `dev-m1-v1`, `dev-m1o-v1` | — |
| `politica` | `ppo`, `heuristic`, `random` | `ppo` |
| `run_id` | un modelo del catálogo (solo con `ppo`) | el modelo servido |

Las suites reservadas (`test-final-…`) nunca se pueden evaluar. El modelo debe haberse entrenado con el mapa de la
suite, si no: 409 `modelo_incompatible`. Los errores de esta parte llegan **de inmediato** (400, 404, 409, 500).

Si todo está bien, la respuesta es **202 Accepted**:

```json
{
  "evaluacion_id": "29B3m5CG9wpv", "estado": "en_cola", "suite_id": "suite-m1b-v1", "politica": "ppo",
  "run_id": "m1b-i1-seed1-best", "model_sha256": "46984e97…", "inferencia": "numpy",
  "escenario": "m1b/cerrado", "catalog_version": "legacy-18", "certificado": true, "determinista": true,
  "episodios": 50, "semillas": [10000, 10049],
  "sondeo": "/evaluaciones/trabajos/29B3m5CG9wpv",
  "progreso": {"episodios_hechos": 0, "episodios_total": 50}, "posicion_en_cola": 1
}
```

**2. Consultar:** `GET` a la ruta que viene en `sondeo` (o `/evaluaciones/trabajos/{evaluacion_id}`). Repite cada
2 a 3 segundos. Esa respuesta tiene el mismo contenido de arriba, más:

| `estado` | Qué significa | Qué más trae |
|---|---|---|
| `en_cola` | Espera su turno (se evalúa de a una) | `posicion_en_cola` |
| `en_curso` | Se está ejecutando | `progreso.episodios_hechos` de `episodios_total` |
| `terminada` | Lista | `resultado`, `segundos`, `terminada_en` |
| `fallida` | No terminó | `error` con `codigo` y `mensaje` |

Resultado de una evaluación terminada:

```json
{"estado": "terminada", "segundos": 25.18,
 "progreso": {"episodios_hechos": 50, "episodios_total": 50},
 "resultado": {
   "resumen": {"success_rate": 1.0, "mean_steps": 106.92, "mean_collisions": 0.0, "mean_deliveries": 3.0, "end_reasons": {"success": 50}},
   "por_episodio": [{"seed": 10000, "success": true, "end_reason": "success", "steps": 107, "collisions": 0, "deliveries": 3}]
 }}
```

`success_rate` va de 0 a 1 (1.0 es 100%). Cada fila de `por_episodio` trae más campos de los mostrados (recompensa,
batería, conteo de acciones…). Con `politica: "random"` el progreso no se puede medir y `episodios_hechos` es
`null` hasta que termina.

**Reglas a tener en cuenta:**

- Una sola evaluación corre a la vez; **hasta 3 pueden esperar**. Con una cuarta: 429 `cola_llena`: avisar al
  usuario y reintentar en un minuto.
- Una evaluación terminada se conserva **30 minutos desde la última consulta**; después responde 404
  `evaluacion_no_encontrada`. Guarda el resultado en la web apenas lo recibas.
- Las evaluaciones y su cola viven en la memoria del servidor: si este se redespliega o se duerme, se pierden.
- `certificado: true` significa suite oficial y catálogo `legacy-18` (el de las evaluaciones certificadas). Los
  episodios usan otro catálogo (`trendy-27-v1`), así que sus números no son comparables con los de una evaluación.

## 7. Episodios: duración y qué se pierde

- Un episodio caduca a los **30 minutos sin que nadie lo consulte** (cada petición lo renueva).
  `caduca_en_s` dice cuántos segundos le quedan.
- Hay un máximo de **200 episodios** a la vez. Si se llena, se descarta el más antiguo que ya terminó; si todos
  siguen en curso, 429 `demasiados_episodios`.
- **Se pierden al redesplegar la API y cuando el servidor se duerme** (15 min sin tráfico). Los episodios viven solo
  en su memoria: no hay base de datos. La respuesta de `GET /episodios/{id}` será 404 `episodio_no_encontrado`.
  Lo que debe hacer la web: avisar y crear uno nuevo con la misma semilla (`seed`), que da el mismo pedido.
- Para detectar un reinicio sin esperar al 404, compara `iniciado_en` de `/health` o `/version` con el valor
  anterior: si cambió, hubo reinicio.
- Lo que **no** se pierde en un reinicio: los modelos, el catálogo, los alias y las evaluaciones guardadas
  (`GET /evaluaciones/{run_id}`); vienen dentro de la imagen del servidor.

## 8. Qué esperar del servidor gratuito

La API corre en el plan gratuito de Render (0.1 de CPU y 512 MB de memoria):

- **Se duerme** tras 15 minutos sin ninguna petición. La primera petición después tendrá que **esperar a que
  despierte**: Render habla de hasta ~1 minuto; lo medimos una vez y tardó unos 18 s (la siguiente petición, ya
  despierto, 0.4 s). Mientras tanto la web puede
  recibir una demora larga o un error de conexión: conviene mostrar un «despertando el servidor…» y reintentar
  `/health` hasta que `precarga` sea `ok`. Si alguien quiere demostrarlo, conviene abrir la URL unos minutos antes.
- **Va más lento mientras evalúa.** Una evaluación ocupa casi toda la CPU. Medido en una simulación del mismo plan:
  con una evaluación en curso, `/health` tarda 0.1 a 0.4 s (normalmente milisegundos), crear un episodio unos 0.8 s
  y crear y correr uno completo unos 2.5 s; la evaluación misma pasa de unos 23 s a unos 27 s. No se queda
  colgada: solo responde más despacio.
- **Tiempos medidos en producción:** correr un episodio completo, 1 a 1.5 s; evaluación oficial de 50 episodios con
  el modelo servido, unos 25 s (con un modelo que falla, como `m1-c3-seed0` con el paso cerrado, unos 75 s);
  evaluación de 10 episodios, unos 5 s.
- **Cuando cambia el modelo servido** (promoción o rollback) el servidor se redespliega: tarda unos 25 s en
  mostrar el modelo nuevo, y los episodios y evaluaciones en memoria se pierden.
- Solo una evaluación corre a la vez, y el plan gratuito no está pensado para mucho tráfico simultáneo.

Recomendaciones para la web: usar `correr` y animar localmente; hacer el sondeo de evaluaciones cada 2 a 3
segundos y no más seguido; no llamar a `/monitoreo` ni `/version` en bucle (cada llamada gasta CPU del plan
gratuito); y mostrar siempre un mensaje claro cuando haya que esperar.

## 9. Capa `/api/*`: el visor de la web actual sobre esta API

Es la capa de compatibilidad: **las mismas rutas, cuerpos y respuestas que la web usa hoy con el `/api` de Vercel**
(el visor, «Cargar en la bodega» y «Evaluar»), pero ejecutadas por esta API. La web solo tiene que cambiar la
dirección base y la forma de guardar la sesión. El visor libre de pedidos (pedido tras pedido con la bodega
compartida, «Generar pedido», pedidos de 1 a 3 productos) y el modo antiguo sin maquillaje **funcionan**, porque se usa el mismo
motor de sesión del visor (`ViewerSession`). Las respuestas son idénticas a las de Vercel (pasos, ruta de referencia,
inventario, eventos); las pruebas lo comparan paso a paso.

### 9.1 Las rutas

| Método | Ruta | Recibe | Devuelve |
|---|---|---|---|
| GET | `/api/layout` | nada (opcional `X-Sesion`) | `layout`, `catalog` (27 productos), `catalog_version`, `layout_sha256`, `available_ppo`, `models` (2 recomendados), `environment_version` |
| GET | `/api/state` | `X-Sesion` (opcional) | el estado de la sesión (ver abajo); **sin cabecera crea una sesión nueva** |
| POST | `/api/reset` | `{orders, policy, blocked, seed, makeup}` o `{policy: "ppo", model, blocked, seed}` | el estado de la misión nueva |
| POST | `/api/step` | `{}` o `{action}` (0 a 7, solo en modo manual) + `X-Sesion` | el estado tras un paso |
| POST | `/api/evaluate` | `{model, blocked, episodes, seed}` | diagnóstico rápido (**no certificado**) |
| GET | `/api/health` | nada | `status`, `environment_version`, `served_models`, `commit`, número de sesiones |

- **El estado** trae lo de siempre: `state`, `info`, `observation`, `policy`, `orders`, `makeup`, `seed`, `done`,
  `terminated`, `truncated`, `last_action`, `last_reward`, `route` y `route_kind` (la ruta de referencia, solo para
  dibujar), `trail`, `events`, `model` (la ficha del modelo, o `null`), `environment_version` y **`sesion_id`** (nuevo).
- `policy` puede ser `heuristic`, `random`, `manual` o `ppo` (esta última **solo con `model`**; ver 9.5). `orders` es
  1 o 2. **Envía siempre todos los campos** en `reset`, como ya hace la web: los que falten toman los valores
  del visor antiguo (`orders` 2, `blocked` true, `policy` heuristic, `seed` 10000, `makeup` false).
- **`layout.models`** lista solo los modelos recomendados que la API puede ejecutar (hoy `m1b-i1-seed1-best`, el de
  producción, y `m1-c3-seed0`), con la misma ficha de siempre: `id`, `nivel`, `estado`, `environment_version`,
  `model_sha256`, `test_final`, etc. Con `{policy: "ppo", model: "<id>"}` también se puede cargar cualquier otro modelo del
  catálogo que `GET /catalogo` marque con `evaluable_con_api: true`.
- **`layout.environment_version`** es la versión del **mapa** (`"0.4.0"`), igual que antes; la del ambiente
  (`"warehouse-v10"`) está en el estado.
- Los cuerpos pesan como máximo 4096 bytes y llevan `Content-Type: application/json`.

### 9.2 Cómo funciona la sesión (`X-Sesion`)

En Vercel la sesión viajaba en una cookie firmada. Entre dos dominios (web en Vercel, API en Render) las cookies no
sirven, así que ahora la sesión es **un identificador que la web guarda y envía en cada petición**:

1. Al abrir la web: `GET /api/layout` (sin sesión) y `GET /api/state` (sin sesión). El segundo **crea la sesión** y
   devuelve su identificador en la cabecera `X-Sesion` y en el cuerpo (`sesion_id`).
2. La web **guarda ese identificador** (propongo `sessionStorage`: sobrevive a recargar la página y se borra al cerrar
   la pestaña).
3. Desde entonces, **toda** petición lleva `X-Sesion: <id>`: `state`, `reset`, `step` (y opcionalmente `layout`).
4. `POST /api/reset` con el identificador reinicia **la misma sesión** (mismo `sesion_id`, y la bodega compartida
   sigue con el stock que quedó). Sin identificador, o con uno desconocido, **crea una sesión nueva** y devuelve su
   identificador: la web debe quedarse con el último que reciba.
5. Cada petición renueva la sesión: **caduca a los 30 minutos sin uso**. Hay un máximo de **100 sesiones**; si se llena se
   descarta la más antigua ya terminada, y si todas están en curso, `429` (`demasiadas_sesiones`).
6. **No llames a `state` sin identificador en bucle:** cada llamada crea una sesión nueva. Llámalo sin identificador
   solo al abrir la web y guarda lo que devuelva.

### 9.3 Ejemplo de uso desde la web

Reemplazo de la función `api()` de `web/src/main.js` (hoy usa `/api/...` del mismo dominio):

```js
const API_BASE = import.meta.env.VITE_API_BASE_URL;                 // sin barra final
const CLAVE_SESION = 'warehouse-sesion';
let sesionId = sessionStorage.getItem(CLAVE_SESION);

async function api(path, body) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (sesionId) headers['X-Sesion'] = sesionId;
  let response;
  try {
    response = await fetch(`${API_BASE}/api/${path}`, {
      method: body === undefined ? 'GET' : 'POST', headers, credentials: 'omit',   // sin cookies
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error('No se pudo conectar con la API. Si estuvo inactiva, puede estar despertando (~20 s): reintenta.');
  }
  const result = await response.json();
  const nueva = response.headers.get('X-Sesion') || result.sesion_id;          // la API la devuelve siempre
  if (nueva && nueva !== sesionId) { sesionId = nueva; sessionStorage.setItem(CLAVE_SESION, nueva); }
  if (!response.ok) {
    if (result.codigo === 'sesion_no_encontrada') { sesionId = null; sessionStorage.removeItem(CLAVE_SESION); }
    const error = new Error(result.error || `HTTP ${response.status}`);        // `error` sigue siendo un texto
    error.codigo = result.codigo;
    throw error;
  }
  return result;
}
```

Pedir lo mismo con `curl` (la sesión va en la cabecera):

```bash
API=https://warehouse-rush-api.onrender.com
curl -s -i $API/api/state | grep -i '^x-sesion'                      # crea la sesión y la devuelve
curl -s -X POST $API/api/reset -H 'Content-Type: application/json' -H "X-Sesion: $ID" \
     -d '{"policy":"ppo","model":"m1b-i1-seed1-best","blocked":true,"seed":10000}'
curl -s -X POST $API/api/step  -H 'Content-Type: application/json' -H "X-Sesion: $ID" -d '{}'
curl -s -X POST $API/api/evaluate -H 'Content-Type: application/json' \
     -d '{"model":"m1b-i1-seed1-best","blocked":true,"episodes":10}'
```

### 9.4 Qué cambia en la web

1. **Dirección:** `fetch` pasa de `/api/...` (mismo dominio) a `${VITE_API_BASE_URL}/api/...`. El prefijo `/api` se conserva.
2. **Sesión:** enviar `X-Sesion` y guardar el identificador (9.2 y 9.3); usar `credentials: 'omit'`. Ya no hay cookie.
3. **Sesión perdida:** manejar el error `sesion_no_encontrada` (9.6).
4. **Errores:** siguen siendo `{"error": "texto"}`, como en Vercel, así que `new Error(result.error)` funciona tal cual. Se
   añade `codigo` (estable) por si quieres distinguir casos.
5. **«Evaluar» rápido:** la respuesta trae **`certificado: false`**, `catalog: "trendy-27-v1"` y una `nota`. Conviene
   mostrar «diagnóstico no certificado» y enviar al usuario a la evaluación oficial (`POST /evaluaciones`, sección 6). Puede
   tardar hasta ~14 s si el modelo falla (unos 5 s si funciona): mostrar un aviso de espera. Corre de a uno: si ya hay otro,
   `429` (`diagnostico_en_curso`).
6. **PPO genérico:** `layout.available_ppo` es `{"1": false, "2": false}`, así que la opción «PPO entrenado» queda
   desactivada con el código actual de la web (se recomienda quitarla). Un `reset` con `policy: "ppo"` sin `model` responde 400.
7. **Modo antiguo sin maquillaje (P1/P2, 1 o 2 pedidos):** sigue funcionando, para que Naomi decida si se conserva.
8. **Ritmo:** cada `step` tarda ~0.1 s de CPU en el servidor más la red (unos 0.2 a 0.4 s). Mantener el ritmo actual (650 ms por
   paso) y no lanzar pasos en paralelo (la web ya usa una bandera `busy`).
9. **Servidor dormido:** la primera petición después de unos 15 min sin uso puede tardar ~18 s. Mostrar «despertando el
   servidor…» en vez de un error.

### 9.5 Diferencias con el `/api` de Vercel

| | Vercel | Render |
|---|---|---|
| Sesión | cookie firmada (2 h) | identificador en `X-Sesion` (30 min sin uso) |
| Tras reiniciar el servidor | la partida sigue (viene en la cookie) | **se pierde** (vive en memoria) |
| Modelos | `configs/modelos_servidos.json` con torch | catálogo de la API con inferencia NumPy |
| PPO genérico del experimento 001 | existía | **ya no existe** |
| Errores | `{"error": "texto"}` | igual, con `codigo` añadido |
| «Evaluar» | síncrono, 1 a 20 episodios | igual, con `certificado: false`; uno a la vez |
| Límite de sesiones | ninguno | 100 |

### 9.6 Qué hacer cuando la sesión se pierde

La sesión vive en la memoria del servidor. Se pierde cuando **el servidor se redespliega**, **se duerme** (15 min sin
tráfico), la sesión **caduca** (30 min sin uso) o se descarta porque el servidor estaba lleno. Entonces `state` y `step`
responden `404` con `codigo: "sesion_no_encontrada"` y el texto «La sesión no existe o caducó…».

Lo que debe hacer la web:

1. Al recibir ese error, **borrar el identificador guardado** (el ejemplo 9.3 ya lo hace) y **avisar al usuario** con un
   mensaje claro, por ejemplo: «La sesión se perdió porque el servidor se reinició o estuvo inactivo. Se reinicia la misión».
2. **Llamar a `POST /api/reset`** con los valores actuales de los controles (política, pasos cerrados, semilla…). `reset` nunca
   da este error: crea una sesión nueva y devuelve su identificador, que la web guarda.
3. Con la **misma semilla** el pedido es el mismo; lo que se pierde es el avance de la misión y el **stock acumulado de la
   bodega compartida** (la sesión nueva empieza con el stock inicial).

```js
async function executeStep(action) {
  /* … */
  try { renderState(await api('step', action === undefined ? {} : { action })); }
  catch (error) {
    if (error.codigo === 'sesion_no_encontrada') { pause(); toast('La sesión se perdió; se reinicia la misión.'); await reset(); }
    else { pause(); toast(error.message); }
  }
}
```

Al abrir la página con un identificador guardado de una sesión que ya no existe, `GET /api/state` responde el mismo error:
trátalo igual (descartar el identificador y llamar a `reset`, o volver a pedir `state` sin identificador). Para saber de antemano
si hubo un reinicio, compara `iniciado_en` de `GET /health` con el valor que viste antes.

### 9.7 Errores de `/api/*`

Todos con la forma `{"error": "texto", "codigo": "…"}`:

| Estado | `codigo` | Cuándo |
|---|---|---|
| 400 | `parametro_invalido` | Cuerpo vacío, mayor de 4096 bytes o que no es un objeto JSON; valores inválidos (`orders` distinto de 1 o 2, `seed` negativa, acción fuera de 0 a 7 o enviada fuera del modo manual…); `policy: "ppo"` sin `model` |
| 400 | `falta_sesion` | `step` sin `X-Sesion` |
| 404 | `sesion_no_encontrada` | `state` o `step` con una sesión que no existe o caducó |
| 404 | `modelo_no_encontrado` | El modelo no existe en el catálogo |
| 404 | `ruta_no_encontrada` | Ruta `/api/...` desconocida |
| 409 | `modelo_incompatible` / `sin_version_numpy` | El modelo es de otra versión del ambiente o no se puede ejecutar |
| 415 | `tipo_no_soportado` | La petición no es `application/json` |
| 429 | `demasiadas_sesiones` | Hay 100 sesiones en curso |
| 429 | `diagnostico_en_curso` | Ya hay un «Evaluar» corriendo |
| 500 | `integridad`, `error_interno` | Fallos internos (por ejemplo, la huella de un modelo no coincide) |

Fuera de `/api/*`, los errores siguen el formato uniforme de la sección 3.

### 9.8 Lo que no incluye

- El PPO genérico de `warehouse-v1` (`experiment-001`), que no es compatible con `warehouse-v10`.
- Sesiones que sobrevivan a un reinicio del servidor (ver 9.6).
- `POST /api/evaluate` **no es la evaluación oficial**: para eso, `POST /evaluaciones` (sección 6).

## 10. Para probar a mano

```bash
curl https://warehouse-rush-api.onrender.com/version
curl -X POST https://warehouse-rush-api.onrender.com/episodios \
     -H 'Content-Type: application/json' -d '{"seed": 10000, "bloqueado": true}'
curl -X POST https://warehouse-rush-api.onrender.com/evaluaciones \
     -H 'Content-Type: application/json' -d '{"suite_id": "suite-m1b-v1"}'
```

En local: `uvicorn api._app:app --port 7860 --workers 1` y usa `http://localhost:7860`. Hay que agregar tu origen a
`CORS_ORIGINS` (por ejemplo `CORS_ORIGINS=http://localhost:5173`) para llamarla desde el navegador.
