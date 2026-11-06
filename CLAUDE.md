# Warehouse Rush · Proyecto final de MLOps

## Qué es
Agente PPO que aprende a recoger paquetes en dos estaciones de recogida y entregarlos
en la estación correcta de una bodega con estanterías y pasillos. La web (Vercel) muestra
la evolución del agente, el catálogo de experimentos, permite cargar modelos históricos y
evaluarlos con su ambiente compatible. Más contexto: skill `warehouse-rush`.

## Estructura
- envs/       ambiente Gymnasium, sensores, recompensa, contrato (envs/CONTRATO.md)
- configs/    perfiles YAML por nivel (n1, n2, n3), hipótesis (experiments/), suites/, criterios.yaml
- pipelines/  train.py, evaluate.py, baselines.py, callbacks.py, compare.py, registry.py, tracking.py, flow.py
- api/        FastAPI: catálogo, carga de modelo, evaluación, episodios
- tests/      pruebas de reglas, observaciones, acciones y terminaciones
- web/        Vite + TypeScript + Three.js
- manifests/  un JSON por modelo recuperable (schema.json)
- docs/       ambiente-v0.1.md, decisiones.md, experimentos.md, resultados/
- warehouse_rush/  prototipo Q-learning heredado (migrar a la estructura de arriba)

## Reglas de trabajo
- La simulación en Python es la autoridad. Three.js solo representa el estado.
- No cambies orden, unidades ni rangos de observación/acción sin subir la versión del ambiente y anotar en docs/decisiones.md.
- Hitos de recompensa se pagan una sola vez por pedido. Recoger y soltar el mismo paquete no da puntos. Entregar solo vale en la estación correcta, dentro del radio y a baja velocidad.
- terminated = éxito o fallo de la misión; truncated = límite de pasos.
- Todo entrenamiento se registra en MLflow: commit, versión del ambiente, config resuelta y su SHA-256, semilla, presupuesto, métricas y modelo.
- Cada modelo final tiene manifiesto en manifests/ (run_id, level_id, environment_version, git_commit, config_sha256, model_uri, model_sha256, normalization_uri, runtime_ref, evaluation_suite_id, seed, parent_run_id).
- Nunca sobrescribas un modelo registrado: crea una versión nueva.
- No subir a Git: .venv/, node_modules/, .env, mlruns/ locales, mlflow.db ni pesos grandes.
- Ramas dev/<nombre>; a main solo por PR con revisión y prueba. Commits en español (feat:, fix:, docs:).
- Runs: <nivel>-<hipótesis>-seed<semilla>, ej. n1-baseline-seed42.

## Comandos
- Pruebas: python -m pytest tests -q
