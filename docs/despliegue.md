# Despliegue del experimento 001

Demo pública: https://warehouse-rush-experiment-001.vercel.app

Proyecto: `warehouse-rush-experiment-001`, cuenta de Angie, entorno Production.
Rama versionada: `dev/angie`. La publicación inicial se realiza con Vercel CLI;
el despliegue automático de Git no está configurado.

Se conserva la simulación Python y el visor Three.js. La versión pública usa una
función Python y un frontend estático en Vercel, sin entrenamiento remoto ni
base de datos. El comando local `view` sigue usando su servidor de desarrollo.

## Arquitectura

- `web/dist/`: frontend generado por Vite.
- `api/index.py`: entrada HTTP de Vercel, delega en `api._cloud`.
- `cloud.py`: restaura un snapshot firmado por visitante, ejecuta el mismo
  `WarehouseRushEnv.step()` y devuelve el siguiente estado.
- `models/experiment-001/`: snapshot real de PPO y manifiesto con hashes.

El estado se conserva en una cookie HttpOnly/SameSite, firmada con HMAC-SHA256.
No se confía en estado enviado sin firma. Cada visitante tiene su misión;
reinicios y cambios de instancia no comparten ni borran el episodio mientras
la cookie sea válida. Caduca tras 2 horas sin renovación. El historial visual
se limita a 64 posiciones; distancia, recompensa y contadores completos se
mantienen. Recargar recupera el episodio. No existe identidad ni clasificación
competitiva persistente: es una demostración académica.

La política aleatoria reconstruye su secuencia desde semilla y pasos; PPO usa el
modelo congelado y recibe sólo su observación. Su estado firmado nunca se usa
para modificar resultados experimentales archivados en `docs/resultados/`.

## Configuración de Vercel

Usar raíz del repositorio, Python 3.12, Node 24 y `vercel.json`:

```text
Install Command: npm ci --prefix web
Build Command: npm run build --prefix web
Output Directory: web/dist
```

Variables sólo del servidor:

- `WAREHOUSE_SESSION_SECRET`: secreto aleatorio de al menos 32 caracteres,
  configurado en Vercel; nunca en Git ni con prefijo de frontend.
- `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`: permite las bibliotecas Python de ML en
  Fluid Compute. El despliegue instala PyTorch CPU en Linux, evitando CUDA.

El backend requiere el modelo pequeño de `models/experiment-001/`, no los
checkpoints ignorados de `artifacts/`. No se ejecuta `train` durante el build ni
al recibir peticiones. `/api/health` identifica versión, experimento y commit.

El repositorio y el servidor local se mantienen independientes del proveedor.
Para entrenamiento largo o varios procesos con estado persistente, un servicio
de contenedores sería más adecuado; este despliegue cubre visualización e
inferencia del primer experimento.

## Verificación local del mismo adaptador

```bash
source .venv/bin/activate
npm ci --prefix web
npm run build --prefix web
python -m api._cloud
# Otra terminal:
WAREHOUSE_TEST_URL=http://127.0.0.1:8090 npm test --prefix web
python -m pytest -q
```

El preview genera una clave efímera local sin imprimirla. En Vercel la clave es
estable y se obtiene de las variables del proyecto. Las pruebas comprueban
aislamiento, firma, expiración, reproducción de Random, misión completa,
recarga y controles de la interfaz.

Referencias: [Python en Vercel](https://vercel.com/docs/functions/runtimes/python),
[funciones de gran tamaño](https://vercel.com/changelog/vercel-functions-can-now-be-up-to-5-gb-in-package-size).

## Modelos servidos (desde 2026-11-18)
La API ejecuta los modelos `recomendado` de `configs/modelos_servidos.json`; sus pesos están en `models/servidos/` (en Git: Vercel no accede a DVC).
Al promover un modelo nuevo: `dvc pull models/<run>.dvc`, actualizar su manifiesto a `recomendado` y correr `python -m pipelines.servir`.
El script comprueba el SHA-256 contra el manifiesto y nunca sobrescribe un peso servido con otro contenido. Prueba: `python -m pytest tests/test_served_models.py`.

## Catálogo de modelos de la web (desde 2026-11-18)
`python -m pipelines.catalogo` regenera `web/public/modelos/catalogo.json` y las curvas a partir de los manifiestos y de MLflow (lectura pública de DagsHub).
Hay que correrlo cada vez que cambie un manifiesto, y antes de `npm run build`. Rutas de la API: `GET health|layout|state`, `POST reset|step|evaluate`.
Pruebas de navegador: con el visor local (`python -m pipelines.cli view --no-open`) correr `npx playwright test` en `web/`. Para el modo nube, levantar `python -c "from api._cloud import preview; preview(8090)"` y correr con `WAREHOUSE_TEST_URL=http://127.0.0.1:8090`.
