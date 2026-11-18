# Warehouse Rush

> **Antes de modificar el proyecto:** lee [AGENTS.md](AGENTS.md). Incluye el relevo de Naomi, el alcance visual, las funcionalidades que deben conservarse y cómo actualizarse desde GitHub y comprobar producción antes de subir cambios.

Proyecto final de MLOps (Universidad Externado de Colombia). Un robot de bodega atiende pedidos de productos de
estantería (3 niveles de altura) con un elevador telescópico y los entrega en una cinta de despacho (ambiente `warehouse-v2`;
la familia `warehouse-v1`, dos estaciones de recogida, se conserva como historia). PPO (Stable-Baselines3) sobre un ambiente Gymnasium; visor Three.js desplegado en Vercel
(https://warehouse-rush-experiment-001.vercel.app); experimentos en MLflow ([DagsHub](https://dagshub.com/mamezquita/Warehouse-Rush.mlflow)); versionado con Git + DVC.

## Estructura
`envs/` ambiente · `configs/` niveles, experimentos, suites, criterios · `pipelines/` entrenamiento, evaluación, tracking ·
`api/` entrada de Vercel y servidor del visor · `tests/` · `web/` Vite+TS+Three.js · `manifests/` modelos recuperables ·
`models/` pesos (DVC; `experiment-001` en Git) · `docs/` ficha del ambiente, decisiones, experimentos, resultados.

## Reproducir
1. Python 3.12: `python3.12 -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\python.exe`)
2. PyTorch CPU: `pip install torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu`
3. `pip install -r requirements.txt`
4. Pruebas: `python -m pytest tests -q`
5. Visor: `npm ci --prefix web && python -m pipelines.cli view` (Node LTS, ver `.nvmrc`)
6. Entrenar (v2): `python -m pipelines.train --config configs/experiments/m1_c0_makeup3.yaml` (los configs `c0`–`c6` son de `warehouse-v1` y ya no entrenan)
7. Pesos grandes: `pip install dvc-s3` (ya en requirements) y `dvc pull` desde el remoto `r2` (Cloudflare R2, bucket `mlops-final-project`). Las credenciales van solo en `.dvc/config.local` (ignorado por Git): `dvc remote modify --local r2 access_key_id ...` y `... secret_access_key ...`; pídelas al equipo. Un modelo concreto: `dvc pull models/<run>.dvc`.
8. MLflow (historial de experimentos, persistente y compartido): [DagsHub](https://dagshub.com/mamezquita/Warehouse-Rush.mlflow), lectura pública sin instalar nada. Para registrar runs: copia `.env.example` a `.env`, pon tu usuario y token de DagsHub (Settings → Tokens) y carga las variables antes de entrenar: `set -a; source .env; set +a`. Sin `MLFLOW_TRACKING_URI` el entrenamiento se detiene (no queda en un sqlite local); `MLFLOW_PERMITIR_LOCAL=1` solo para pruebas deliberadas. El historial anterior (96 runs del `mlflow.db` local) se copió con `python -m pipelines.migrar_mlflow`; mapa de ids en `docs/resultados/mlflow-migracion.json`; copia del sqlite original en DVC (`dvc pull mlflow.db.dvc mlruns.dvc`).

Modelo actual, hiperparámetros y reentrenamiento: [docs/modelo-actual.md](docs/modelo-actual.md).
Ambiente: contrato [envs/CONTRATO.md](envs/CONTRATO.md), ficha vigente [docs/ambiente-v0.2.md](docs/ambiente-v0.2.md) (v1: [ambiente-v0.1.md](docs/ambiente-v0.1.md)). Despliegue: [docs/despliegue.md](docs/despliegue.md).
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
mapa amplio, elevador, planificación de carga y cinta/caja de Angie. Las misiones
mantienen sus 18 identificadores TMP y las cookies existentes. Los modelos se
asocian visualmente sin cambiar las transacciones; el catálogo permite consultar
los 27 assets. Ver [integración y alcance](docs/integracion-rosa.md).

Esta rama desactiva sus despliegues automáticos de Vercel en `vercel.json`.
Para verla en el Mac: actualizar `dev/naomi`, compilar con `npm run build --prefix web`
y ejecutar `python -m pipelines.cli view --no-open` desde el entorno Python.


## Catálogo operativo de 27 productos

Las sesiones nuevas ya generan pedidos con los 27 productos definitivos del PDF.
Cada producto tiene nombre, SKU TRD, estante/nivel, modelo y stock inicial fijo entre
5 y 10 unidades: **202 unidades** en total. Cada kit se cuenta como una unidad.
La distribución, los stocks exactos y la compatibilidad con sesiones TMP anteriores
se documentan en [catálogo operativo](docs/catalogo-operativo.md).

Después de actualizar el repositorio en el Mac, recompilar y reiniciar el servidor
para crear un inventario local con el nuevo catálogo. Las sesiones antiguas firmadas
conservan sus productos y cantidades; una sesión nueva/privada utiliza TRD. Generar
otro pedido no repone stock ni convierte productos antiguos automáticamente.


## Revisar modelos desde la web
«Modelos y experimentos ↗» abre el catálogo de los 82 modelos, generado con `python -m pipelines.catalogo` a partir de los manifiestos y de MLflow.
Cada ficha muestra hipótesis, cambios frente a la base, run, semilla, presupuesto, estado y enlace a MLflow, evaluación con causas de fin, test final y curva de entrenamiento.
Los dos modelos recomendados se pueden **cargar en la bodega** y **evaluar** (10 episodios en el servidor, con latencia de inferencia y hash servido), y hasta 3 modelos se pueden **comparar**.
La barra muestra el modo activo: control manual, aleatorio, referencia, evaluación o entrenamiento.
Enlaces directos: `?modelo=m1b-i1-seed1-best&cerrado=1&semilla=10000` carga el modelo y `?catalogo=m1-c3-seed0` abre su ficha.

### Catálogo en el ambiente y en la web
El catálogo es un parámetro del escenario (`envs.inventory.CATALOGS`): `warehouse-v10` se entrenó y evaluó con
`legacy-18` (18 productos TMP), y `make_env` lo mantiene para que las suites y los tests finales sigan siendo reproducibles.
La web usa `trendy-27-v1`, también al ejecutar los modelos recomendados. Diagnóstico sobre las 50 semillas de la suite:
100% de éxito con el catálogo de 27 en los dos modelos y escenarios, sin degradación frente a `legacy-18`
([resultados](docs/resultados/eval/catalogo-trendy-27/resultados.json)).
