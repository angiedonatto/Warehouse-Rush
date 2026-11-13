# Warehouse Rush

> **Antes de modificar el proyecto:** lee [AGENTS.md](AGENTS.md). Incluye el relevo de Naomi, el alcance visual, las funcionalidades que deben conservarse y cómo actualizarse desde GitHub y comprobar producción antes de subir cambios.

Proyecto final de MLOps (Universidad Externado de Colombia). Un robot de bodega atiende pedidos de productos de
estantería (3 niveles de altura) con un elevador telescópico y los entrega en una cinta de despacho (ambiente `warehouse-v2`;
la familia `warehouse-v1`, dos estaciones de recogida, se conserva como historia). PPO (Stable-Baselines3) sobre un ambiente Gymnasium; visor Three.js desplegado en Vercel
(https://warehouse-rush-experiment-001.vercel.app); experimentos en MLflow; versionado con Git + DVC.

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
7. Pesos grandes: `dvc pull` (remoto por acordar)

Modelo actual, hiperparámetros y reentrenamiento: [docs/modelo-actual.md](docs/modelo-actual.md).
Ambiente: contrato [envs/CONTRATO.md](envs/CONTRATO.md), ficha vigente [docs/ambiente-v0.2.md](docs/ambiente-v0.2.md) (v1: [ambiente-v0.1.md](docs/ambiente-v0.1.md)). Despliegue: [docs/despliegue.md](docs/despliegue.md).
Decisiones: [docs/decisiones.md](docs/decisiones.md). Variables: `.env.example`.
