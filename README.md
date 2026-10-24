# Warehouse Rush v0.2 — visor 3D y ambiente v0.1

Demo del experimento 001: **https://warehouse-rush-experiment-001.vercel.app**

Un robot recoge y entrega paquetes en una bodega 2D mediante un entorno
Gymnasium. Incluye políticas Random y BFS, entrenamiento PPO con Stable-Baselines3,
CLI, pruebas y evaluación reproducible. Cinemática discreta de 1 m y 1 s por paso.

La versión 0.2 añade una interfaz **Three.js** local basada en la referencia
industrial: bodega 3D, cuatro cámaras, telemetría y minimapa. El ambiente de
aprendizaje mantiene su versión 0.1 y las mismas reglas y resultados.

El primer experimento está congelado en
[`experiments/experiment-001/`](experiments/experiment-001/README.md), con su
modelo PPO real, hashes, semillas y resultados. El modelo pesa aproximadamente
170 KiB y permite inferencia reproducible en el despliegue.

La configuración para publicar frontend y Python está en `vercel.json`; ver
[despliegue y sesiones por visitante](docs/despliegue.md).

## Abrir la interfaz 3D

Con el entorno Python ya instalado, desde la raíz del repositorio:

```bash
source .venv-rl/bin/activate
python -m warehouse_rush.cli view
```

Se abre **http://127.0.0.1:8080** en el navegador. La primera vez prepara las
dependencias de la interfaz y la compila automáticamente; requiere Node.js
reciente (verificado con Node 24.17.0). Si prefieres prepararla antes:

```bash
npm ci --prefix web
npm run build --prefix web
python -m warehouse_rush.cli view --port 8080 --no-open
```

Pulsa **Iniciar** para ver al heurístico completar los dos pedidos con bloqueo.
Puedes pausar, avanzar **Un paso**, reiniciar, seleccionar agente y cambiar misión
o bloqueo. Cambiar estos últimos prepara un episodio nuevo. Las miniaturas
cambian entre cámara isométrica, primera persona, seguimiento lateral y estación.
Arrastra la escena para orbitar y usa la rueda para acercar.

El modo **Control manual** habilita cinco botones y teclas W/A/D/S/E. Ruta BFS y
sensores se pueden mostrar u ocultar. La ruta dibujada siempre es una referencia
BFS; no se atribuye al modelo PPO. El PPO de un pedido está disponible cuando
existe su modelo guardado y conserva su comportamiento real de frenado.

La interfaz representa las transiciones ejecutadas por el mismo `WarehouseRushEnv`
del CLI; no reimplementa la misión en JavaScript. El mapa y las estaciones proceden
del JSON canónico. Detalles en [docs/visor-v0.2.md](docs/visor-v0.2.md).

## Instalar

Desde una terminal nueva, dentro del repositorio y en `dev/angie`:

```bash
git switch dev/angie
python3.12 -m venv .venv-rl
source .venv-rl/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps -e .
```

Python 3.12 es la versión verificada en macOS Intel; las versiones fijadas también
evitan la incompatibilidad de PyTorch con Python 3.13 en ese equipo. Se usa un
único entorno local, `.venv-rl/`. Las dependencias directas están en `requirements.txt` y
`pyproject.toml`; `requirements-lock.txt` registra todas las versiones ejecutadas.
El snapshot inicial de dependencias se conserva en `docs/requirements-original.txt`.

## Usar y verificar

```bash
python -m warehouse_rush.cli map
python -m warehouse_rush.cli map --blocked
python -m warehouse_rush.cli validate
python -m warehouse_rush.cli demo-transitions --steps 5
python -m warehouse_rush.cli play --policy random --orders 1 --delay 0
python -m warehouse_rush.cli play --policy heuristic --orders 2 --delay 0.05
python -m warehouse_rush.cli play --policy heuristic --orders 2 --blocked --no-render
```

El mapa JSON es la fuente compartida del simulador, CLI y pruebas. `--orders 1`
es P1→entrega; `--orders 2` añade P2→entrega en ese orden. `--blocked` cierra un
tramo y mantiene una ruta alternativa. El robot debe frenar y mirar hacia una
estación adyacente para interactuar. `--delay` controla la animación de terminal
y `--no-render` muestra únicamente el resumen final.

## Repetir los experimentos

```bash
# Integración corta; modelo separado del principal mediante seed=7.
python -m warehouse_rush.cli train --algo ppo --orders 1 --timesteps 128 --n-steps 64 --batch-size 32 --seed 7

# Experimento principal: 20 000 pasos efectivos, un pedido, semilla 42.
python -m warehouse_rush.cli train --algo ppo --orders 1 --timesteps 20000 --seed 42

# 20 episodios × 3 políticas × 2 escenarios, semillas 10000–10019.
python -m warehouse_rush.cli compare --orders 1 --episodes 20 --seed-start 10000

# Ver exclusivamente el modelo aprendido y evaluar un escenario concreto.
python -m warehouse_rush.cli play --policy ppo --orders 1 --delay 0.05
python -m warehouse_rush.cli evaluate --policy ppo --orders 1 --episodes 20 --output results/ppo-only
python -m warehouse_rush.cli evaluate --policy ppo --orders 1 --blocked --episodes 20 --output results/ppo-blocked

# Baselines para la misión de dos pedidos; no implica haber entrenado PPO nivel 2.
python -m warehouse_rush.cli compare --orders 2 --policies random heuristic --episodes 20 --output results/level2
```

Todos los comandos se ejecutan desde la raíz. Las carpetas de entrenamiento
tienen nombres únicos para conservar ejecuciones previas. El alias
`artifacts/models/ppo_orders1_seed42.zip` apunta mediante copia al último modelo
final de esa misión/semilla; `--model ruta.zip` selecciona otro. Los modelos y
entornos virtuales se ignoran en git. Los modelos no se descargan del repositorio:
se generan localmente al entrenar. No se requiere red para entrenar o evaluar una
vez instaladas las dependencias.

## Resultados y documentación

- [Informe medido de las tres políticas](results/report.md).
- [Episodios CSV](results/evaluation.csv) y [configuración, agregados y hashes JSON](results/evaluation.json).
- [Curva de entrenamiento](results/training_curve.png).
- [Baselines de dos pedidos](results/level2/report.md).
- [Ficha académica: estado, 22 observaciones, acciones, recompensas y transiciones](docs/ambiente-v0.1.md).

Cada entrenamiento registra metadatos, duración real, versiones, Monitor,
`progress.csv`, evaluaciones periódicas, checkpoints y modelo final. Las
comparaciones registran errores reales y salen con código no cero si alguna
combinación falla. Para comparar configuraciones distintas usa carpetas
`--output` diferentes.

PPO sólo decide con observaciones normalizadas; el BFS es un baseline que conoce
mapa y estado completos. Un entrenamiento que termine sin errores puede tener
0% de éxito. El informe presenta esa diferencia y no sustituye PPO por la
heurística. La escena 3D de v0.2 interpola la cinemática discreta; no incorpora
física continua ni infraestructura cloud.

En el experimento ejecutado de 20 000 pasos (semilla 42, 118.10 s), PPO obtuvo
**0% de éxito** y permaneció frenando en BASE. El heurístico logró **100%** con y
sin bloqueo (47 y 63 pasos para un pedido); Random obtuvo 0%. Son 20 episodios por
combinación con semillas 10000–10019. El ciclo completo funciona; el modelo corto
todavía no aprende la misión. El informe explica también por qué una recompensa
mayor bajo bloqueo no implica una ruta más eficiente.
