# Decisiones técnicas

| Fecha | Autor | Decisión | Motivo |
|---|---|---|---|
| 2026-11-06 | lis | Estructura del repo según enunciado sec. 07 (envs/ configs/ pipelines/ tests/ web/ manifests/ docs/ + api/) | Una carpeta por rol para no pisarse en Git |
| 2026-11-06 | lis | El prototipo Q-learning queda en warehouse_rush/ hasta migrar a PPO (SB3) | El enunciado toma PPO como referencia; otros algoritmos requieren justificación |
| 2026-11-06 | lis | Python 3.12 fijo (.python-version); el .venv actual es 3.14 y debe recrearse | Acuerdo del equipo: Python 3.12 + PyTorch CPU |
| PENDIENTE | equipo | Dónde vive MLflow persistente, remoto de DVC, host de la API HTTPS, Prefect vs Airflow | Acordar con el docente |
