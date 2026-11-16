> **Actualización 2026-11-15 (noche, incidente N3).** Modelo **`recomendado` para el nivel `m1b`** (mapa con muro con el paso (6,14) abierto o cerrado): `m1b-i1-seed1-best` = mejor checkpoint de `m1b-i1-seed1` (`models/m1b-i1-seed1/best/best_model.zip`, sha256 `46984e97…`, manifiesto `manifests/m1b-i1-seed1-best.json`): ajuste fino de `m1-c3-seed0` con el paso cerrado en la mitad de los ambientes, paso 3 582 240. **Test final reservado `test-final-m1b-v1`: 100/100 abierto (81.5 pasos) y 100/100 cerrado (106.0 pasos), 0 choques, 0 inválidas** (heurística 78.3 / 102.0). Es el modelo de producción; `m1-c3-seed0` es el rollback. La receta `m1b-i1` se rechazó (una de 3 semillas se atasca contra un muro): se certifica el artefacto, no la receta. Detalles: `docs/experimentos.md` («Selección declarada de un modelo `m1b`»).

> **Actualización 2026-11-15 (`warehouse-v10`, nivel `m1`, mapa con muro).** Primer modelo **`recomendado`**: `m1-c3-seed0` (`models/m1-c3-seed0/model.zip`, manifiesto `manifests/m1-c3-seed0.json`, config `configs/experiments/m1_c3_largo_seed0.yaml`): PPO [64,64], receta base (invalid −0.2, collision −1, `progress` 0.3), `ent_coef` 0, parada por estancamiento 100, 1 802 240 pasos. `suite-m1-v1` 98%; **test final reservado 100/100, 0 choques, 0 inválidas, 90.6 pasos** (heurística 80.2). Elegido por regla declarada entre 15 semillas (3 completan la misión); certifica el artefacto, no la receta. Detalles: `docs/experimentos.md` («Selección declarada de semilla y test final reservado»).

> **Actualización 2026-11-13 (`warehouse-v2`).** El ambiente de entrenamiento es ahora `warehouse-v2` (solo maquillaje): observación `Box(27)`, acciones `Discrete(8)`, mapa 25 × 19, batería 180 y 400 pasos (contrato: `envs/CONTRATO.md`). El modelo descrito abajo (experiment-001) y los runs `n1-c0…c6` pertenecen a `warehouse-v1` (Box(22), Discrete(5)) y **no son compatibles** con v2. El primer run v2 es `m1-c0-seed0` (`configs/experiments/m1_c0_makeup3.yaml`, mismos hiperparámetros que C0); sus resultados están en `docs/experimentos.md`. Nivel `m1`: 3 productos aleatorios por episodio.

# Modelo actual, reentrenamiento e hiperparámetros

## Qué es el modelo (experimento 001, `models/experiment-001/ppo-orders1-seed42.zip`)
- **Algoritmo:** PPO de Stable-Baselines3 2.4.1, `MlpPolicy`, CPU, PyTorch 2.2.2. Actor y crítico separados, ambos `[64, 64]`.
- **Observación:** `Box(22,)` float32 en [0,1] (dos componentes relativas en [-1,1]): 8 rayos, objetivo relativo (dx, dy), orientación one-hot, velocidad, batería, carga, etapa, tiempo restante. Ver `docs/ambiente-v0.1.md` §4.
- **Acción:** `Discrete(5)`: AVANZAR, GIRAR_IZQUIERDA, GIRAR_DERECHA, FRENAR, INTERACTUAR.
- **Entrenado en:** N1 (1 pedido, pasillo abierto), semilla 42, 20 000 pasos, 118 s.
- **Resultado:** 0% de éxito; el modelo aprendió a frenar siempre en BASE (retorno -25.5). El heurístico BFS logra 100% y el aleatorio 0%. Es el baseline de partida, no un modelo útil.
- **Entorno:** `ENV_VERSION = "warehouse-v1"` (ficha v0.1.0), mapa `configs/layout_v0.1.json`, `max_steps=250`, batería 100.

## Recompensa (`envs/rewards.py`, `RewardConfig`)
recogida +10, entrega +30, misión completa +50, progreso +0.3 por celda de acercamiento al objetivo, tiempo -0.1/paso, batería -0.02 por unidad, choque -5, interacción inválida -2. Los hitos se pagan una vez; las validaciones impiden ciclos rentables.

## Hiperparámetros
| Parámetro | Experimento 001 | Plan (C0, `configs/experiments/`) | Para qué sirve |
|---|---|---|---|
| learning_rate | 3e-4 | 3e-4 | tamaño del paso del optimizador |
| n_steps × n_envs | 500 × 1 | 2048 × 4 | experiencia recogida antes de cada actualización |
| batch_size | 100 | 64 | tamaño del minibatch (debe dividir n_steps × n_envs) |
| n_epochs | 10 | 10 | pasadas por lote |
| gamma | 0.99 | 0.99 (C2: 0.995) | horizonte: cuánto valen recompensas lejanas |
| gae_lambda | 0.95 | 0.95 | sesgo/varianza de la ventaja |
| clip_range | 0.2 | 0.2 | cuánto puede cambiar la política por actualización |
| ent_coef | 0.01 | 0.0 (C1: 0.01) | exploración |
| vf_coef / max_grad_norm | 0.5 / 0.5 | 0.5 / 0.5 | peso del crítico / recorte de gradiente |
| net_arch | [64, 64] | [64, 64] | tamaño de la red |
| presupuesto | 20 000 | 200 000 (N1), 1 000 000 (N2), +300 000 (N3) | pasos de ambiente |

Dado que 20 000 pasos no bastaron, lo primero a probar es el presupuesto del plan (200 000 en N1), `ent_coef` 0.01 (C1) y, si no despega, la recompensa de progreso. El PPO se queda quieto porque con 250 pasos el castigo por tiempo domina: documentar cualquier cambio de recompensa como nueva versión del ambiente (`warehouse-v2`).

## Cómo lanzar un reentrenamiento
```bash
source .venv/bin/activate
python -m pipelines.train --config configs/experiments/c0_baseline_n1.yaml      # entrena y registra en MLflow
python -m pipelines.train --config configs/experiments/c1_entropia_n1.yaml
dvc repro train_c0                                                             # lo mismo, con DVC
python -m pipelines.train --config <yaml> --timesteps 8192                     # solo prueba de humo
```
- Cada YAML en `configs/experiments/` es un run: cambia **una** dimensión y trae su hipótesis escrita antes de entrenar. Nombre del run: `<nivel>-<id>-seed<semilla>`; para otra semilla copia el YAML con otro `seed`.
- Se registra en MLflow (experimento `warehouse-n1/n2/n3`): params, tags (`git_commit`, `environment_version`, `config_sha256`, `nivel`, `hipotesis`, `parent_run_id`, `tipo`, `estado`), `config.json`, modelo + `model_sha256`, curvas y estado `fallido`/`interrumpido` si algo falla. URI: variable `MLFLOW_TRACKING_URI` (por defecto `sqlite:///mlflow.db`, local).
- **Continuar desde un checkpoint (C3, C4):** poner en `parent_run_id` el nombre del run padre (p. ej. `n1-c0-seed0`); carga `models/<parent>/model.zip`. El contador de pasos es acumulado (padre + nuevos).
- Salidas: `models/<run>/model.zip` (+ `best/`, `checkpoints/`), `docs/resultados/training/<run>/` (metadata, curva, métricas). No se sobrescribe: si el run existe, falla.
- Referencias y evaluación hoy: `python -m pipelines.cli evaluate --policy ppo|random|heuristic --episodes 50 --seed-start 10000`. Pendiente (R2): que `evaluate.py` lea las suites de `configs/suites/` y escriba `evaluacion.json` por run.

## Aún no hecho (según el plan)
`pipelines/compare.py` y `callbacks.py` (R2); tracking completo, registro de modelos, manifiestos con SHA-256 para cada run, Prefect, API FastAPI (R3); remotos de MLflow y DVC por acordar.
