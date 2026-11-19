# Imagen de la API de Warehouse Rush para Render (docs/decisiones.md, 2026-11-18).
# Se construye con api/publicar.sh desde `git archive` de un commit (solo lo versionado) más VERSION.json:
#   docker build -f api/Dockerfile -t ghcr.io/<usuario>/warehouse-rush-api:<sha7> <contexto>
# Sin torch, SB3, MLflow ni DVC: inferencia NumPy (models/numpy/), sin credenciales dentro de la imagen.
# Capas de la más estable a la más cambiante: un cambio solo en manifests/ (promoción o rollback) reconstruye
# únicamente las dos últimas capas.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PORT=7860
WORKDIR /app
RUN useradd --create-home --uid 10001 api

# 1) Dependencias: cambian solo si cambia requirements-api.txt (mismas versiones que requirements.txt).
COPY requirements-api.txt ./
RUN pip install -r requirements-api.txt

# 2) Código y configuración: simulación (envs), evaluación y registro (pipelines), API, mapas, niveles y suites.
#    Las suites test-final* nunca entran (.dockerignore; además están fuera de Git).
COPY envs/ envs/
COPY pipelines/ pipelines/
COPY api/ api/
COPY configs/ configs/

# 3) Evaluaciones congeladas (GET /evaluaciones/{run_id}); cambian solo con experimentos nuevos.
COPY docs/resultados/eval/ docs/resultados/eval/

# 4) Lo que cambia con una promoción o un rollback: políticas NumPy, manifiestos, catálogo, alias y commit.
COPY models/numpy/ models/numpy/
COPY manifests/ manifests/
COPY VERSION.json ./

USER api
# EXPOSE es solo informativo (documenta el puerto por defecto; no abre ni publica nada). El puerto real es $PORT:
# 7860 por defecto (ENV de arriba, para `docker run -p 7860:7860` en local) y 10000 en Render, que fija PORT y
# enruta el tráfico a ese puerto.
EXPOSE 7860
# Un solo worker: episodios y evaluaciones viven en la memoria de un proceso. Render fija $PORT; detrás de su proxy
# se aceptan las cabeceras X-Forwarded-*.
CMD ["sh", "-c", "exec uvicorn api._app:app --host 0.0.0.0 --port \"${PORT}\" --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
