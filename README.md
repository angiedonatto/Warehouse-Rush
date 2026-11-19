# Warehouse Rush

Proyecto final de **MLOps · Universidad Externado de Colombia**.

Warehouse Rush simula una bodega de maquillaje donde un robot con bandeja telescópica debe recoger productos de las estanterías y entregarlos en una cinta de despacho. El ambiente utiliza **Gymnasium**, los agentes se entrenan con **PPO de Stable-Baselines3** y la visualización se implementa con **Three.js**.

Este documento describe la entrega del **19 de noviembre de 2026**, según el informe final.

## Enlaces de entrega

| Recurso | Enlace |
|---|---|
| Web | https://warehouse-rush-psi.vercel.app |
| API | https://warehouse-rush-api.onrender.com |
| Documentación interactiva de la API | https://warehouse-rush-api.onrender.com/docs |
| Repositorio | https://github.com/angiedonatto/Warehouse-Rush |
| Release | https://github.com/angiedonatto/Warehouse-Rush/releases/tag/v1.0 |
| MLflow / DagsHub | https://dagshub.com/mamezquita/Warehouse-Rush.mlflow |

La versión de entrega es **`v1.0`**, cuyo tag apunta al commit:

```text
f72f0a20b4306dbaed251d0896645b00a92800cd
```

El contenido posterior de `main` puede incluir cambios adicionales.

## Instalación

### Requisitos

- Python 3.12.
- Git.
- Node.js LTS y npm. Referencia: [.nvmrc](.nvmrc).
- Para entrenar y recuperar los pesos originales: acceso a DagsHub y al remoto DVC de Cloudflare R2.

### Obtener la versión entregada

Ejecutar en una carpeta nueva para no modificar un checkout con trabajo pendiente:

```bash
git clone --branch v1.0 https://github.com/angiedonatto/Warehouse-Rush.git Warehouse-Rush-v1.0
cd Warehouse-Rush-v1.0
```

El tag permite consultar y reproducir la entrega. No es una rama de desarrollo.

### Crear el entorno virtual

En macOS o Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

En Windows, desde PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

### Instalar dependencias

Para ejecutar únicamente la API y la web:

```bash
python -m pip install -r requirements-api.txt
npm ci --prefix web
```

La API utiliza modelos NumPy incluidos en Git; para esta modalidad no necesita PyTorch, DVC ni credenciales de entrenamiento.

Para disponer del entorno completo de experimentación:

```bash
python -m pip install -r requirements.txt
npm ci --prefix web
```

Las versiones están fijadas en:

- [requirements.txt](requirements.txt).
- [requirements-api.txt](requirements-api.txt).
- [web/package-lock.json](web/package-lock.json).

## Ejecución

Los comandos siguientes se ejecutan desde la raíz del repositorio. Los ejemplos de variables en línea utilizan Bash o zsh, disponibles en macOS y Linux.

### API local

En una primera terminal, con el entorno virtual activo:

```bash
CORS_ORIGINS=http://127.0.0.1:5173 WAREHOUSE_PRECARGAR=0 python -m uvicorn api._app:app --host 127.0.0.1 --port 7860 --workers 1
```

Documentación de la API local:

```text
http://127.0.0.1:7860/docs
```

`WAREHOUSE_PRECARGAR=0` desactiva la precarga al arrancar; los modelos se cargan cuando se necesitan.

### Web local

En una segunda terminal:

```bash
VITE_API_BASE_URL=http://127.0.0.1:7860 npm run dev --prefix web
```

Abrir:

```text
http://127.0.0.1:5173
```

Si Vite utiliza otro puerto, actualizar `CORS_ORIGINS` y reiniciar la API. Para CORS, `localhost` y `127.0.0.1` son orígenes diferentes.

La API publicada en Render solo acepta los orígenes configurados. Para desarrollar localmente, utilizar la API local o coordinar la autorización del nuevo origen.

### Funcionalidades de la web

- Bodega 3D con estética rosa y lavanda inspirada en Trendy.
- Catálogo de 27 productos, organizado en seis categorías.
- Modelos GLB y consulta visual de productos.
- Misiones con inventario, recogida, elevador y despacho.
- Control manual y políticas de referencia.
- Catálogo de modelos históricos, carga de los modelos compatibles y comparación.
- Evaluaciones oficiales asíncronas.
- Diagnóstico rápido identificado como **no certificado**.
- Identidad del modelo servido y monitoreo.

El catálogo operativo `trendy-27-v1` tiene entre 5 y 10 unidades iniciales por producto: **202 unidades en total**. Generar otro pedido dentro de una sesión vigente no repone el stock.

Documentación: [catálogo operativo](docs/catalogo-operativo.md), [entrega visual](docs/entrega-naomi.md) y [licencias](docs/licencias.md).

## Variables

Utilizar [.env.example](.env.example) como plantilla. Si se necesita un archivo `.env`, crearlo sin sobrescribir configuraciones locales existentes.

| Variable o configuración | Descripción |
|---|---|
| `VITE_API_BASE_URL` | Origen de la API, sin barra final. En local: `http://127.0.0.1:7860`. En producción: `https://warehouse-rush-api.onrender.com`. |
| `CORS_ORIGINS` | Orígenes autorizados para llamar a la API desde el navegador. |
| `WAREHOUSE_PRECARGAR` | `0` desactiva la precarga de modelos al arrancar; `1` la activa. |
| `MLFLOW_TRACKING_URI` | Dirección del servidor de MLflow en DagsHub. |
| `MLFLOW_TRACKING_USERNAME` | Usuario autorizado de DagsHub. |
| `MLFLOW_TRACKING_PASSWORD` | Token de DagsHub, utilizado únicamente en backend. |
| `MLFLOW_PERMITIR_LOCAL` | `1` permite deliberadamente tracking local para pruebas; no sustituye el historial compartido. |
| Credenciales DVC del remoto `r2` | Se guardan en `.dvc/config.local`, ignorado por Git. |

Configuración pública de referencia:

```env
VITE_API_BASE_URL=https://warehouse-rush-api.onrender.com
MLFLOW_TRACKING_URI=https://dagshub.com/mamezquita/Warehouse-Rush.mlflow
```

Para cargar las variables de `.env` antes de entrenar en Bash o zsh:

```bash
set -a
source .env
set +a
```

**Seguridad y despliegue:**

- No subir tokens ni credenciales al repositorio.
- Las variables `VITE_*` llegan al navegador; nunca deben contener secretos.
- Vite incorpora `VITE_API_BASE_URL` durante la compilación.
- Cambiar esa variable en Vercel requiere una nueva compilación y despliegue.

Detalles: [contrato de API](docs/api-contrato.md) y [despliegue](docs/despliegue.md).

## Arquitectura

**Python es la autoridad de la simulación. Three.js representa el estado recibido.**

Vercel sirve la web estática. Render es el único servidor de modelos, inferencia, simulación, evaluaciones y monitoreo.

```text
Configuración YAML + ambiente Gymnasium
                  |
           Entrenamiento PPO ------> MLflow / DagsHub
                  |                  runs, métricas y registro
                  v
          Pesos originales --------> DVC / Cloudflare R2
                  |
         Exportación y verificación
                  v
  Modelos NumPy + manifiestos + alias en Git
                  |
                  v
         API FastAPI en Render <---- Web Three.js en Vercel
                  |
       simulación, evaluación y monitoreo

Prefect orquesta el proceso de validación, pruebas,
modelo, evaluación, registro, decisión, publicación
del catálogo y verificación de la versión servida.
```

### Componentes

| Componente | Ubicación y responsabilidad |
|---|---|
| Ambiente | `envs/`: dinámica, observaciones, acciones, inventario y recompensas. |
| Configuración | `configs/`: mapas, niveles, experimentos, suites y criterios. |
| Entrenamiento | `pipelines/train.py`. |
| Evaluación y comparación | `pipelines/evaluate.py` y `pipelines/compare.py`. |
| Pipeline y registro | `pipelines/flow.py` y `pipelines/registry.py`. |
| Modelos | `models/`: referencias DVC y exportaciones NumPy. |
| Trazabilidad | `manifests/`: identidad, configuración, hashes, suites y alias. |
| API | `api/_app.py`, `api/_modelos.py`, `api/_episodios.py` y `api/_visor.py`. |
| Web | `web/`: Vite, Three.js, controles y catálogos. |
| Documentación y evidencia | `docs/` y `docs/resultados/`. |

### API y sesiones

Rutas principales:

- `/version`: identidad de la versión y del modelo servido.
- `/catalogo`: modelos y estados.
- `/evaluaciones`: evaluaciones oficiales asíncronas.
- `/episodios`: ejecución de episodios.
- `/monitoreo`: métricas operativas.
- `/api/*`: compatibilidad con el visor.

El visor guarda el identificador de partida en `sessionStorage` y lo envía mediante la cabecera `X-Sesion`, con `credentials: 'omit'`.

Las sesiones viven en memoria. Si el servidor se reinicia o pierde la sesión, el avance y el inventario acumulado de esa partida no se recuperan.

### Ambiente y niveles de dificultad

Ambiente vigente: **`warehouse-v10`**.

- Bodega de 25 × 19.
- Seis estanterías con tres niveles de altura.
- Capacidad de tres productos.
- Batería inicial de 180.
- Máximo de 400 pasos.
- Observación `Box(27)` en `[0,1]`, sin incluir el mapa.
- Ocho acciones: avanzar, girar a cada lado, frenar, cargar, descargar, subir y bajar.

El episodio termina por éxito, batería agotada u objetivo inalcanzable. Alcanzar el límite de pasos produce truncamiento.

| Nivel | Identificador | Escenario | Suite |
|---|---|---|---|
| N1 | `m1o` | Mapa abierto, sin muro interior. | `suite-m1o-v1` |
| N2 | `m1` | Mapa con muro y paso `(6,14)` abierto. | `suite-m1-v1` |
| N3 | `m1b` | Mismo mapa con el paso `(6,14)` cerrado. | `suite-m1b-v1` |

Las suites utilizan 50 semillas fijas. Las recompensas y sus parámetros se versionan por experimento.

Documentación: [contrato del ambiente](envs/CONTRATO.md), [ficha vigente](docs/ambiente-v0.10.md) y [niveles](docs/niveles.md).

## Reproducción

### 1. Comprobar la versión

En la copia clonada desde el tag:

```bash
git rev-parse HEAD
git show --no-patch v1.0
```

El commit esperado es:

```text
f72f0a20b4306dbaed251d0896645b00a92800cd
```

Cada modelo debe ejecutarse con la versión del ambiente y la configuración indicadas en su manifiesto.

### 2. Recuperar los modelos

Con las dependencias completas y el acceso al remoto DVC configurado:

```bash
dvc pull models/m1-c3-seed0.dvc models/m1b-i1-seed1.dvc
python -m pipelines.registry estado
```

Para recuperar todos los artefactos versionados:

```bash
dvc pull
```

| Uso | Modelo | Artefacto original |
|---|---|---|
| Producción | `m1b-i1-seed1-best` | `models/m1b-i1-seed1/best/best_model.zip` |
| Anterior / rollback | `m1-c3-seed0` | `models/m1-c3-seed0/model.zip` |

Los manifiestos incluyen hashes SHA-256, configuración, ambiente, suite y procedencia.

Las observaciones ya están acotadas en `[0,1]`. Ambos modelos finales indican `normalization_uri: null` y no utilizan `VecNormalize`; no requieren un archivo externo de normalización.

La API utiliza exportaciones NumPy verificadas frente a SB3 en **636 986 pasos sin diferencias de acción**, según el informe final.

### 3. Entrenar un experimento

Con MLflow configurado:

```bash
python -m pipelines.train --config configs/experiments/m1_c3_largo_seed0.yaml
```

Este comando entrena y registra un run. No es necesario entrenar para abrir la demo.

El informe registra:

- 94 runs en MLflow.
- 82 manifiestos.
- Pesos de 90 runs en DVC.

Estos números corresponden a conjuntos distintos.

Ejemplos de configuraciones:

| Configuración | Hipótesis o cambio | Familia de runs |
|---|---|---|
| [c3](configs/experiments/m1_c3_largo_seed0.yaml) | Aumentar presupuesto sin añadir los términos de recompensa e4. | `m1-c3-*` |
| [e4](configs/experiments/m1_e4x_seed0.yaml) | Añadir progreso Manhattan y ajuste de altura. | `m1-e4x-*`, `m1-e4y-*` |
| [c4](configs/experiments/m1_c4_entropia_seed1.yaml) | Aumentar entropía para favorecer exploración. | `m1-c4-*` |
| [i1](configs/experiments/m1b_i1_incidente_seed1.yaml) | Ajustar el modelo alternando paso abierto y cerrado. | `m1b-i1-*` |

Las hipótesis y criterios se fijaron antes de entrenar. Los runs rechazados o fallidos se conservan.

Detalles: [experimentos](docs/experimentos.md).

### 4. Evaluar y comparar

Para reconstruir la comparación de finalistas con los resultados disponibles:

```bash
python -m pipelines.compare --config configs/comparaciones/finalistas-m1-v1.yaml
```

Desde la web se pueden lanzar evaluaciones oficiales. La API crea un trabajo asíncrono y permite consultar su progreso hasta finalizar.

Es necesario distinguir:

| Modalidad | Catálogo y propósito |
|---|---|
| Evaluación oficial | Suite fija y catálogo `legacy-18`, para reproducibilidad. |
| Visor y episodios | Catálogo `trendy-27-v1`. |
| Diagnóstico rápido | No certificado; no sustituye una evaluación oficial. |
| Test final reservado | Evidencia independiente usada una sola vez. |

Las semillas de los test finales se mantienen fuera del repositorio. Como esos test ya se utilizaron, una selección nueva requiere un test nuevo.

### 5. Pipeline y rollback

Consultar los comandos disponibles y el registro:

```bash
python -m pipelines.flow --help
python -m pipelines.registry estado
```

El pipeline de Prefect implementa ocho etapas:

1. Validar.
2. Probar.
3. Entrenar o cargar.
4. Evaluar.
5. Registrar.
6. Decidir.
7. Publicar el catálogo.
8. Verificar la versión servida.

Existe además un flujo de rollback. La publicación y el rollback modifican el modelo servido; no son necesarios para probar la web local.

El informe documenta una prueba real de rollback por cambio de alias y redeploy en aproximadamente **25 segundos**.

Procedimiento y evidencia:

- [Rollback](docs/rollback.md).
- [Relevo R3](docs/relevo-r3.md).
- [Ejecuciones del pipeline](docs/resultados/flujo/).
- [Despliegues](docs/resultados/despliegues/).

### 6. Pruebas automáticas

Con el entorno completo instalado:

```bash
python -m pytest tests -q -n 6 --dist loadfile
```

El informe final registra **373 pruebas automáticas**. Este número corresponde a la entrega documentada, no a una nueva ejecución realizada al redactar este README.

Algunas verificaciones opcionales requieren recuperar previamente los pesos originales.

Para las pruebas de navegador de `v1.0`, iniciar la API en el puerto 7860 con:

```bash
CORS_ORIGINS=http://127.0.0.1:8080 WAREHOUSE_PRECARGAR=0 python -m uvicorn api._app:app --host 127.0.0.1 --port 7860 --workers 1
```

En otra terminal:

```bash
cd web
VITE_API_BASE_URL=http://127.0.0.1:7860 npx vite build --mode e2e
npx vite preview --host 127.0.0.1 --port 8080
```

Con ambos servidores activos, ejecutar desde la raíz en una tercera terminal:

```bash
WAREHOUSE_TEST_URL=http://127.0.0.1:8080 WAREHOUSE_API_URL=http://127.0.0.1:7860 npm test --prefix web
```

Si falta el navegador de Playwright, instalarlo desde `web/`:

```bash
npx playwright install chromium
```

Estas instrucciones corresponden al tag `v1.0`; otras ramas pueden utilizar fixtures diferentes.

## Resultados principales

Resultados documentados en el informe final:

| Evidencia | Resultado |
|---|---|
| Receta c3 en N2 | 1 de 5 semillas alcanza al menos 50% de éxito; media de receta: 20%. |
| Receta e4 en N2 | 2 de 6 semillas alcanza al menos 50%; media de receta: 30%. |
| Referencia c4 | 0 de 4 semillas alcanza al menos 50%. |
| Selección entre c3 y e4 | Diferencia no distinguible; desempate por simplicidad a favor de c3. |
| `m1-c3-seed0`, test final N2 | 100/100 episodios, 0 choques y 0 acciones inválidas. |
| Degradación al cerrar el paso | `m1-c3-seed0` pasa de 98% a 0% en la suite. |
| `m1b-i1-seed1-best`, test final | 100/100 abierto y 100/100 cerrado, sin choques ni acciones inválidas. |
| Evaluación oficial desde la web | 50/50 y 106,92 pasos medios; reproduce la evaluación registrada del modelo de producción. |

La receta de intervención `i1` fue rechazada por su variabilidad y choques. Una selección declarada de un checkpoint concreto sí superó el test final.

**Se certifican artefactos concretos, no la fiabilidad general de la receta.** Solo 3 de 15 semillas completaron la misión del mapa con muro a 1,8 millones de pasos.

La heurística BFS es una referencia privilegiada: dispone de información que el agente no observa y no constituye evidencia de aprendizaje por refuerzo.

Evidencia: [comparación de finalistas](docs/resultados/comparacion/finalistas-m1-v1/report.md), [modelo actual](docs/modelo-actual.md) y [resultados](docs/resultados/).

## Limitaciones

- Alta variabilidad entre semillas de entrenamiento.
- La observación no incluye el mapa y el agente puede memorizar rutas.
- Los modelos del mapa abierto no se transfieren directamente al mapa con muro.
- La evaluación determinista puede ocultar comportamientos que aparecen al muestrear acciones.
- Los test finales reservados ya fueron utilizados.
- Render Free se duerme tras unos 15 minutos sin tráfico y tarda alrededor de 20 segundos en despertar.
- Una evaluación oficial de 50 episodios tarda aproximadamente 25 segundos en el caso medido del modelo de producción; otros modelos pueden tardar más.
- Las sesiones, trabajos y métricas en memoria se pierden al reiniciar o dormir el servidor.
- Queda código heredado por retirar, como `api/_cloud.py`, `pipelines/servir.py` y `models/servidos/`.
- El informe deja pendiente confirmar la infraestructura con el docente.

## Equipo y contribuciones

| Integrante | Rol | Aportes principales según el informe |
|---|---|---|
| Angie Donato | R1 · Ambiente y reglas | Ambiente Gymnasium, inventario, pedidos, bandeja, contrato inicial, heurística, pruebas y revisión de PR. |
| Lis Sánchez | R2 · Entrenamiento y experimentos | Suites, hipótesis y runs, versiones v2–v10, comparación de finalistas, test final, intervención, DVC/DagsHub e integración final y despliegue v1.0. |
| Miguel Amézquita | R3 · Versionado, pipeline y API | MLflow/DagsHub, Prefect, registro, rollback, FastAPI en Render, inferencia NumPy y contrato de API. |
| Naomi Mosquera | R4 · Web y despliegue | Escena visual, selección y catálogo de 27 productos Trendy, modelos GLB e interfaz. |

Se utilizaron asistentes de código. Las decisiones y sus motivos quedan registrados en [docs/decisiones.md](docs/decisiones.md).

Antes de contribuir, consultar [AGENTS.md](AGENTS.md). Licencias de assets y dependencias: [docs/licencias.md](docs/licencias.md).
