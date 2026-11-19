"""requirements-api.txt (imagen de la API en Render) es un subconjunto exacto de requirements.txt, sin torch.

Mismas versiones que el entorno de entrenamiento y evaluación: la API ejecuta la misma simulación (envs/) y la misma
evaluación (pipelines/evaluate.py), así que una versión distinta de numpy o gymnasium podría cambiar resultados.
"""
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
PROHIBIDOS = ("torch", "stable-baselines3", "mlflow", "mlflow-skinny", "prefect", "dvc", "dvc-s3", "matplotlib")


def _requisitos(nombre: str) -> dict[str, str]:
    salida = {}
    for linea in (REPO / nombre).read_text().splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        coincide = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s;]+)", linea)
        assert coincide, f"{nombre}: '{linea}' debe fijar una versión exacta (paquete==versión)"
        clave = re.sub(r"[-_.]+", "-", coincide.group(1)).lower()  # nombre normalizado (PEP 503)
        assert clave not in salida, f"{nombre}: {clave} repetido"
        salida[clave] = coincide.group(2)
    return salida


def test_api_es_subconjunto_exacto_de_requirements():
    completo, api = _requisitos("requirements.txt"), _requisitos("requirements-api.txt")
    faltan = sorted(set(api) - set(completo))
    distintas = {p: (v, completo[p]) for p, v in api.items() if p in completo and completo[p] != v}
    assert not faltan, f"no están en requirements.txt: {faltan}"
    assert not distintas, f"versiones distintas (api, completo): {distintas}"


def test_api_no_lleva_torch_ni_herramientas_de_entrenamiento():
    api = _requisitos("requirements-api.txt")
    assert not [p for p in PROHIBIDOS if p in api]
    assert {"fastapi", "uvicorn", "numpy", "gymnasium", "pyyaml", "jsonschema"} <= set(api)
