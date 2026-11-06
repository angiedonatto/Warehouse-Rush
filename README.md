# Warehouse Rush

Proyecto final de MLOps (Universidad Externado de Colombia). Agente PPO en una bodega: recoger paquetes
en dos estaciones y entregarlos en la correcta. Web en Vercel, experimentos en MLflow, versionado con Git + DVC.

## Estructura
`envs/` ambiente · `configs/` experimentos, suites y criterios · `pipelines/` entrenamiento y evaluación · `api/` FastAPI ·
`tests/` · `web/` Vite+TS+Three.js · `manifests/` modelos recuperables · `docs/` decisiones y resultados ·
`warehouse_rush/` prototipo Q-learning heredado.

## Reproducir (borrador; verificar y actualizar)
1. Python 3.12: `python -m venv .venv`
2. PyTorch CPU: `pip install torch --index-url https://download.pytorch.org/whl/cpu`
3. `pip install -r requirements.txt` (pendiente regenerar con torch, SB3, fastapi, prefect, pytest)
4. Web: Node LTS (`.nvmrc`), `cd web && npm ci && npm run build`
5. Modelos grandes: `dvc pull`

Variables: ver `.env.example`. Decisiones: `docs/decisiones.md`.
