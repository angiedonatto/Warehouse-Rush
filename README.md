# Warehouse Rush

> **Antes de modificar el proyecto:** lee [AGENTS.md](AGENTS.md). Incluye el relevo de Naomi, el alcance visual, las funcionalidades que deben conservarse y cómo actualizarse desde GitHub y comprobar producción antes de subir cambios.

Proyecto final de MLOps (Universidad Externado de Colombia). Un robot de bodega atiende pedidos de productos de
estantería (3 niveles de altura) con un elevador telescópico y los entrega en una cinta de despacho (ambiente vigente `warehouse-v10`,
mapa con muro; `warehouse-v1` a `v9` se conservan como historia con sus etiquetas `env/warehouse-vN`). Niveles: N1 mapa abierto, N2 mapa con muro, N3 paso (6,14) cerrado ([docs/niveles.md](docs/niveles.md)).
Modelos recomendados: `m1b-i1-seed1-best` (producción, N3) y `m1-c3-seed0` (N2, rollback). PPO (Stable-Baselines3) sobre un ambiente Gymnasium; visor Three.js desplegado en Vercel
(https://warehouse-rush-psi.vercel.app); experimentos en MLflow ([DagsHub](https://dagshub.com/mamezquita/Warehouse-Rush.mlflow)); versionado con Git + DVC.

## Estructura
`envs/` ambiente · `configs/` niveles, experimentos, suites, criterios · `pipelines/` entrenamiento, evaluación, tracking ·
`api/` entrada de Vercel y servidor del visor · `tests/` · `web/` Vite+TS+Three.js · `manifests/` modelos recuperables ·
`models/` pesos (DVC; `experiment-001` en Git) · `docs/` ficha del ambiente, decisiones, experimentos, resultados.

## Arquitectura
| Capa | Dónde | Qué hay |
|---|---|---|
| Web, catálogo y comparación | Vercel (estático, `web/dist`) | Vite + Three.js: bodega 3D, catálogo de productos (Naomi) y catálogo «Modelos y experimentos» (`web/public/modelos/catalogo.json`, generado por `pipelines/catalogo.py`) |
| Simulación e inferencia de esta web | Render (`VITE_API_BASE_URL`) | API Python de Miguel; sesión en memoria identificada mediante `X-Sesion`, sin cookies. Visor `/api/*`, identidad `/version`, catálogo `/catalogo` y monitoreo `/monitoreo`. [Integración y configuración](docs/web-render.md). |
| Modelos servidos | Git (`models/servidos/`, `configs/modelos_servidos.json`) | Los recomendados de `warehouse-v10`, con SHA-256 verificado al cargar (`pipelines/servir.py`) |
| Pesos de todos los runs | DVC → Cloudflare R2 (remoto `r2`) | `models/<run>.dvc`; `dvc pull` |
| Experimentos y registro | MLflow en DagsHub (lectura pública) | Runs, métricas y artefactos; Model Registry `warehouse-m1` y `warehouse-m1b` con alias `recomendado` |
| Identidad de modelos | Git (`manifests/`) | Un manifiesto por modelo: run, ambiente, config y su hash, pesos, suite, decisión |
| Entrenamiento y evaluación | PC del equipo | `pipelines/train.py` y `pipelines/evaluate.py`, suites fijas en `configs/suites/` |
| Orquestación | Pendiente (R3) | Flujo Prefect: validar → probar → entrenar o cargar → evaluar → registrar → decidir → publicar → verificar lo servido |

```
entrenamiento (PC) ──► MLflow/DagsHub (runs, registro) ──► manifiestos (Git) ──► pipelines/catalogo.py ──► web (Vercel)
        │                                                        │
        └──► pesos ──► DVC/R2                    pipelines/servir.py ──► models/servidos ──► API (Render) ◄── web
```
Licencias de assets y dependencias: [docs/licencias.md](docs/licencias.md).

## Reproducir
1. Python 3.12: `python3.12 -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\python.exe`)
2. PyTorch CPU: `pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu`
3. `pip install -r requirements.txt`
4. Pruebas: `python -m pytest tests -q`
5. Web conectada a Render: `npm ci --prefix web` y `VITE_API_BASE_URL=https://warehouse-rush-api.onrender.com npm run dev --prefix web` (Node LTS, ver `.nvmrc`). Para una API local compatible, ver [configuración](docs/web-render.md).
6. Entrenar (v10): `python -m pipelines.train --config configs/experiments/m1_c3_largo_seed0.yaml` (receta del modelo recomendado de N2; hipótesis de cada config en [docs/experimentos.md](docs/experimentos.md); los configs `c0`–`c6` son de `warehouse-v1` y ya no entrenan)
7. Pesos grandes: `pip install dvc-s3` (ya en requirements) y `dvc pull` desde el remoto `r2` (Cloudflare R2, bucket `mlops-final-project`). Las credenciales van solo en `.dvc/config.local` (ignorado por Git): `dvc remote modify --local r2 access_key_id ...` y `... secret_access_key ...`; pídelas al equipo. Un modelo concreto: `dvc pull models/<run>.dvc`.
8. MLflow (historial de experimentos, persistente y compartido): [DagsHub](https://dagshub.com/mamezquita/Warehouse-Rush.mlflow), lectura pública sin instalar nada. Para registrar runs: copia `.env.example` a `.env`, pon tu usuario y token de DagsHub (Settings → Tokens) y carga las variables antes de entrenar: `set -a; source .env; set +a`. Sin `MLFLOW_TRACKING_URI` el entrenamiento se detiene (no queda en un sqlite local); `MLFLOW_PERMITIR_LOCAL=1` solo para pruebas deliberadas. El historial anterior (96 runs del `mlflow.db` local) se copió con `python -m pipelines.migrar_mlflow`; mapa de ids en `docs/resultados/mlflow-migracion.json`; copia del sqlite original en DVC (`dvc pull mlflow.db.dvc mlruns.dvc`).

Modelo actual, hiperparámetros y reentrenamiento: [docs/modelo-actual.md](docs/modelo-actual.md).
Ambiente: contrato [envs/CONTRATO.md](envs/CONTRATO.md), ficha vigente [docs/ambiente-v0.10.md](docs/ambiente-v0.10.md) (anteriores: `docs/ambiente-v0.1.md` a `v0.9.md`). Despliegue: [docs/despliegue.md](docs/despliegue.md).
Decisiones: [docs/decisiones.md](docs/decisiones.md). Variables: `.env.example`.

## Catálogo y estética de Trendy (Naomi)

Esta rama integra los **27 productos del PDF de Naomi**, organizados en seis
categorías, con modelos Three.js, assets GLB descargables y una bodega en tonos
rosa y lavanda. «Explorar los 27 productos» abre el catálogo 3D con búsqueda y filtros.
Las misiones conservan Gymnasium y el inventario real por sesión.

Ver [entrega Naomi](docs/entrega-naomi.md) para el catálogo completo, referencias,
ubicaciones, regeneración de assets y verificaciones.


## Versión integrada de Naomi

`dev/naomi` reúne la interfaz rosa y el catálogo visual de 27 productos con el
mapa amplio, elevador, planificación de carga y cinta/caja de Angie. La integración
inicial con los 18 identificadores TMP está documentada como historia
en [integración y alcance](docs/integracion-rosa.md). El catálogo operativo actual usa
27 SKU TRD; la conexión de la web con Render usa `X-Sesion`, sin cookies.

Esta rama desactiva sus despliegues automáticos de Vercel en `vercel.json`.
Para verla en el Mac: actualizar `dev/naomi` y ejecutar el comando de la sección
«Reproducir», paso 5. La configuración de Vercel y las pruebas están en
[Web conectada a Render](docs/web-render.md).


## Catálogo operativo de 27 productos

Las sesiones nuevas ya generan pedidos con los 27 productos definitivos del PDF.
Cada producto tiene nombre, SKU TRD, estante/nivel, modelo y stock inicial fijo entre
5 y 10 unidades: **202 unidades** en total. Cada kit se cuenta como una unidad.
La distribución, los stocks exactos y la compatibilidad con sesiones TMP anteriores
se documentan en [catálogo operativo](docs/catalogo-operativo.md).

Generar otro pedido conserva el inventario de la sesión vigente en Render. Si el
servidor pierde la sesión, la web avisa y crea una misión con stock inicial; el avance
y el inventario acumulado de esa sesión no se recuperan.


## Revisar modelos desde la web
«Modelos y experimentos ↗» abre el catálogo de los 82 modelos, generado con `python -m pipelines.catalogo` a partir de los manifiestos y de MLflow.
Cada ficha muestra hipótesis, cambios frente a la base, run, semilla, presupuesto, estado y enlace a MLflow, evaluación con causas de fin, test final y curva de entrenamiento.
Los modelos que la API identifica como `evaluable_con_api` se pueden **cargar en la bodega** y ejecutar en un **diagnóstico no certificado** (10 episodios, con latencia de inferencia y hash servido); hasta 3 modelos se pueden **comparar**. Las evaluaciones registradas y el test final se muestran por separado.
La barra muestra el modo activo: control manual, aleatorio, referencia, evaluación o entrenamiento.
Enlaces directos: `?modelo=m1b-i1-seed1-best&cerrado=1&semilla=10000` carga el modelo y `?catalogo=m1-c3-seed0` abre su ficha.

### Catálogo en el ambiente y en la web
El catálogo es un parámetro del escenario (`envs.inventory.CATALOGS`): `warehouse-v10` se entrenó y evaluó con
`legacy-18` (18 productos TMP), y `make_env` lo mantiene para que las suites y los tests finales sigan siendo reproducibles.
La web usa `trendy-27-v1`, también al ejecutar los modelos recomendados. Diagnóstico sobre las 50 semillas de la suite:
100% de éxito con el catálogo de 27 en los dos modelos y escenarios, sin degradación frente a `legacy-18`
([resultados](docs/resultados/eval/catalogo-trendy-27/resultados.json)).
