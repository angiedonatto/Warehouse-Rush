# Despliegue del experimento 001

Demo pública actual (warehouse-v10): https://warehouse-rush-psi.vercel.app — ver «Despliegue de warehouse-v10» al final.
Demo histórica del experimento 001: https://warehouse-rush-experiment-001.vercel.app

> **Estado actual (2026-11-19):** una sola arquitectura. Vercel sirve **solo la web** (`web/dist`); la simulación, los
> modelos, las evaluaciones, el monitoreo y las rutas `/api/*` del visor viven en la API FastAPI de Render
> (`https://warehouse-rush-api.onrender.com`, `docs/api-contrato.md`), a la que apunta `VITE_API_BASE_URL`. La función
> Python de Vercel (`api/index.py`, `api/requirements.txt`, `functions` y `rewrites` de `vercel.json`) se retiró; lo que
> sigue sobre ella es historia. Ver «Despliegue de la web contra Render» al final.

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

## Despliegue de warehouse-v10 (2026-11-18)
URL pública: **https://warehouse-rush-psi.vercel.app** (proyecto `warehouse-rush`, equipo Vercel de Lis `lis-team2`).
El sitio anterior (`warehouse-rush-experiment-001.vercel.app`, cuenta de Angie) queda como historia del experimento 001.

- Commit desplegado en producción: `920f028` (rama `dev/lis`, en GitHub), deployment `dpl_Hwt2SPGieA27WTL8jYgcu8SHDamQ`;
  `/api/health` lo confirma. Deploys anteriores (para rollback): `49b8463` (`dpl_5DjgXk6Eh1SiMd6A6w1njNopoeFe`) y `1af8cf6` (`dpl_AUWE3KkZg24X6m6u3CiaCaiP6Bw7`).
- `920f028` corrige el desfase de la escena 3D al hacer scroll (canvas dentro de `#stage`; miniaturas y retrato en canvas 2D propios).
  Medido en producción con Playwright: 0 de 61 frames desfasados (antes 4 de 61, hasta 30 px).
- Se despliega desde un clon limpio del commit (`git clone --branch dev/lis . <tmp>` y `vercel deploy` dentro), no desde la carpeta de trabajo:
  con `.vercelignore` la CLI ignora `.gitignore` y subiría checkpoints locales y la suite reservada `configs/suites/test-final*`.
- La función usa `api/requirements.txt` (solo inferencia, torch CPU); el `requirements.txt` de la raíz es el entorno de desarrollo completo.
- Variables (Production y Preview): `WAREHOUSE_SESSION_SECRET` (aleatorio, 64 caracteres, sensible) y `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`.
- Verificación tras el deploy: `/api/health` → `warehouse-v10`; `/api/layout` sirve `m1b-i1-seed1-best` y `m1-c3-seed0` con el `model_sha256`
  de sus manifiestos; `POST /api/evaluate` 20 episodios N3 cerrado en 4,1 s (100 %, 0 choques, inferencia 0,55 ms/paso, 0 errores);
  sesión interactiva `reset`/`step` con cookie firmada OK.
- Identidad del deploy: por CLI, Vercel deja `VERCEL_GIT_COMMIT_SHA` vacío, así que se despliega con
  `vercel deploy --prod --env WAREHOUSE_DEPLOY_COMMIT=$(git rev-parse --short HEAD)` y `/api/health` devuelve ese `commit`
  más `served_models` (id, estado y `model_sha256` de cada modelo servido). Solo se despliegan commits ya subidos a GitHub.
- Rollback de la web: `vercel rollback <deployment anterior>` o `vercel promote <url>` en el proyecto `warehouse-rush`.

## Despliegue de la web contra Render (2026-11-19)
- Commit desplegado en producción: `7af0570` (`main`, merge del PR #6), deployment `dpl_HQf84Do7RC3bBDKsSHodzfow7M7q`
  (`warehouse-rush-2cf8pgnz8-lis-team2.vercel.app`), alias `warehouse-rush-psi.vercel.app` y `warehouse-rush-lis-team2.vercel.app`.
  Anterior (para rollback): `920f028`, `dpl_Hwt2SPGieA27WTL8jYgcu8SHDamQ` (`warehouse-rush-43328jtkh-lis-team2.vercel.app`).
- La web llama a la API de Render (`VITE_API_BASE_URL=https://warehouse-rush-api.onrender.com`, definida en Vercel para
  Production y Preview; se lee al compilar). Sesión sin cookies: identificador en `sessionStorage` y cabecera `X-Sesion`.
- Desde un clon limpio de `main`: `vercel link --yes --scope lis-team2 --project warehouse-rush` crea un `.env.local` con
  `VERCEL_OIDC_TOKEN`; **borrarlo antes de desplegar** (con `.vercelignore` la CLI no respeta `.gitignore`). Luego
  `vercel deploy --prod --yes --scope lis-team2 --env WAREHOUSE_DEPLOY_COMMIT=$(git rev-parse --short HEAD)`.
- Verificación en producción, con Playwright contra `warehouse-rush-psi.vercel.app` y CORS real (Chromium sin cambios):
  10 de 10 (más 1 omitida por diseño: el PPO genérico ya no existe). Carga del visor, `reset`, pasos, play y pausa, modo
  manual, paso cerrado, «Cargar en la bodega» con `m1b-i1-seed1-best` (pedido completo en 111 pasos), diagnóstico no
  certificado, modelo servido y monitoreo, aislamiento entre visitantes y recarga con la misma sesión, sesión caducada.
- CORS de Render: permite `warehouse-rush-psi.vercel.app` y `warehouse-rush-experiment-001.vercel.app`; **no** el alias
  `warehouse-rush-lis-team2.vercel.app` ni las URL de cada deployment o preview (la página carga, pero el navegador bloquea
  la API). Para probar previews hay que agregar `CORS_ORIGIN_REGEX` en Render.
- Rollback de la web: `vercel promote https://warehouse-rush-43328jtkh-lis-team2.vercel.app --scope lis-team2` (vuelve a la
  web que usaba el `/api` de Vercel; solo sirve mientras ese deployment exista). Rollback del modelo servido: `docs/rollback.md`.
- Retiro de la función de Vercel: en `dev/lis-cierre` (se aplica en el siguiente despliegue). `api/_viewer.py` se conserva:
  es el motor de sesiones de la capa `/api/*` de Render (`api/_visor.py`) y de `python -m pipelines.cli view`.

## Release v1.0: una sola arquitectura en producción (2026-11-19)
- Commit desplegado en producción: `f72f0a2` (`main`, merge del PR #8; etiqueta `v1.0`), deployment
  `dpl_AKyYGiC6AuZ7XoPjgVPSDeiqrF1c` (`warehouse-rush-eipbt7pw6-lis-team2.vercel.app`), alias `warehouse-rush-psi.vercel.app`.
  Anterior (para rollback): `7af0570`, `dpl_HQf84Do7RC3bBDKsSHodzfow7M7q` (`warehouse-rush-2cf8pgnz8-lis-team2.vercel.app`).
- Incluye el PR #7 (función de Vercel retirada, modelos históricos en la web) y el PR #8 (evaluación oficial con progreso).
  Verificado en producción: `/api/health` y `/api/state` de Vercel responden 404 (Vercel solo sirve la web) y la página
  publicada llama a `https://warehouse-rush-api.onrender.com`.
- Pruebas en producción (Playwright, Chromium sin cambios, CORS real contra Render `8b49d63`): 5 de 5. Catálogo y carga
  de `m1b-i1-seed1-best` hasta completar el pedido, modelo histórico `m1-c3-seed1` (carga, diagnóstico, recarga, enlace
  directo), evaluación oficial en `suite-m1b-v1` (100 %, 106.92 pasos, igual a la registrada), sesión sin cookies con el
  rótulo «EN LÍNEA», y pasos/play/pausa/reset.
- Release: https://github.com/angiedonatto/Warehouse-Rush/releases/tag/v1.0
- Rollback de la web: `vercel promote https://warehouse-rush-2cf8pgnz8-lis-team2.vercel.app --scope lis-team2`.

