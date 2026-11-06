# Decisiones técnicas

| Fecha | Autor | Decisión | Motivo |
|---|---|---|---|
| 2026-11-06 | lis | Estructura del repo según enunciado sec. 07 (envs/ configs/ pipelines/ tests/ web/ manifests/ docs/ + api/) | Una carpeta por rol para no pisarse en Git |
| 2026-11-06 | lis | Python 3.12 fijo (.python-version); el .venv actual es 3.14 y debe recrearse | Acuerdo del equipo: Python 3.12 + PyTorch CPU |
| PENDIENTE | equipo | Dónde vive MLflow persistente, remoto de DVC, host de la API HTTPS, Prefect vs Airflow | Acordar con el docente |
| 2026-11-06 | lis | Se integra dev/angie (ambiente, PPO, visor Three.js, Vercel) reubicado en la estructura del plan: src/warehouse_rush -> envs/ (env, layout, rewards), pipelines/ (train, evaluate, baselines=policies, cli), api/ (_cloud, _viewer, index); results/ -> docs/resultados/; experiments/experiment-001 -> manifests/experiment-001.json + models/experiment-001/ + docs/experimento-001.md | La estructura del plan manda; no se cambia la estructura, se adapta el código |
| 2026-11-06 | lis | Se eliminan pyproject.toml, requirements-lock.txt y el prototipo Q-learning; queda solo requirements.txt congelado (Python 3.12) | El plan pide requirements.txt; PPO con SB3 es la referencia del enunciado |
| 2026-11-06 | lis | Versiones fijadas a las de experiment-001 (torch 2.2.2 CPU, SB3 2.4.1, numpy 1.26.4, gymnasium 1.0.0) más mlflow, dvc, prefect, fastapi | El modelo del experimento 001 debe reproducirse con las versiones con que se entrenó |
| 2026-11-06 | lis | Archivos de api/ que no son entrypoint llevan prefijo _ (api/_cloud.py, api/_viewer.py) | Vercel convierte cada .py de api/ en una función; el prefijo _ lo evita |
| 2026-11-06 | lis | ENV_VERSION = "warehouse-v1" en envs/__init__.py (la ficha sigue en 0.1.0) | El plan usa warehouse-v1, v2... para familias de modelos |
| 2026-11-06 | lis | Niveles en configs/niveles.yaml: N1 = 1 pedido, N2 = 2 pedidos, N3 = 2 pedidos con pasillo cerrado | La guía R2 propone 3 pedidos en N2, pero el ambiente v0.1 soporta 1 o 2; pendiente con R1 |
| 2026-11-06 | lis | train.py acepta --config (YAML de configs/experiments/) y registra en MLflow con los tags del plan; pipelines/tracking.py mínimo (R3 lo extiende) | El plan: sin hiperparámetros a mano, config SHA-256, un experimento MLflow por nivel |
| 2026-11-06 | lis | El snapshot models/experiment-001/*.zip (170 KiB) se versiona en Git por excepción | El despliegue en Vercel necesita el modelo y no ejecuta dvc pull |
