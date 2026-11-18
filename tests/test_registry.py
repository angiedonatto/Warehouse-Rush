"""Registro de modelos (pipelines/registry.py): catálogo, alias, promoción, rollback y SHA-256.

Las pruebas usan una copia de manifiestos reales con pesos falsos de pocos bytes (su sha256 se recalcula),
así no dependen de DVC ni de la red. Las dos últimas comprueban el registro real del repositorio.
"""
import json
import shutil
from pathlib import Path

import pytest

from pipelines import registry as R
from pipelines.tracking import sha256_file

REPO = Path(__file__).resolve().parents[1]
RUNS = ("m1-c3-seed0", "m1b-i1-seed1-best", "m1-c3-seed1", "m1-c4-seed1", "m1o-e4l-seed0")


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "manifests").mkdir()
    shutil.copy(REPO / "manifests/schema.json", tmp_path / "manifests/schema.json")
    shutil.copy(REPO / "manifests/experiment-001.json", tmp_path / "manifests/experiment-001.json")
    for run in RUNS:
        manifest = json.loads((REPO / f"manifests/{run}.json").read_text())
        weights = tmp_path / manifest["model_uri"]
        weights.parent.mkdir(parents=True, exist_ok=True)
        weights.write_bytes(f"pesos falsos de {run}".encode())
        manifest["model_sha256"] = sha256_file(weights)
        (tmp_path / f"manifests/{run}.json").write_text(json.dumps(manifest))
    return tmp_path


@pytest.fixture
def inicializado(raiz):
    R.inicializar_aliases(produccion="m1b-i1-seed1-best", anterior_produccion="m1-c3-seed0",
                          motivo="prueba", autor="test", raiz=raiz)
    return raiz


def leer(raiz, nombre):
    return json.loads((raiz / "manifests" / nombre).read_text())


def test_verificar_modelo_detecta_hash_y_ausencia(raiz):
    assert R.verificar_modelo("m1-c3-seed0", raiz=raiz)["ok"]
    (raiz / "models/m1-c3-seed0/model.zip").write_bytes(b"alterado")
    alterado = R.verificar_modelo("m1-c3-seed0", raiz=raiz)
    assert not alterado["ok"] and "no coincide" in alterado["error"]
    (raiz / "models/m1-c3-seed0/model.zip").unlink()
    ausente = R.verificar_modelo("m1-c3-seed0", raiz=raiz)
    assert not ausente["ok"] and not ausente["presente"]


def test_manifiesto_invalido_o_legado_queda_excluido(raiz):
    validos, excluidos = R.listar_manifiestos(raiz)
    assert set(validos) == set(RUNS)
    assert [e["archivo"] for e in excluidos] == ["manifests/experiment-001.json"]
    with pytest.raises(R.RegistroError, match="no coincide con el nombre"):
        shutil.copy(raiz / "manifests/m1-c3-seed0.json", raiz / "manifests/otro.json")
        R.cargar_manifiesto("otro", raiz)


def test_inicializar_toma_los_recomendados_y_no_se_repite(inicializado):
    ranuras = leer(inicializado, "aliases.json")["ranuras"]
    assert ranuras == {"m1": {"actual": "m1-c3-seed0", "anterior": None},
                       "m1b": {"actual": "m1b-i1-seed1-best", "anterior": None},
                       "produccion": {"actual": "m1b-i1-seed1-best", "anterior": "m1-c3-seed0"}}
    with pytest.raises(R.RegistroError, match="ya existe"):
        R.inicializar_aliases(produccion="m1-c3-seed0", motivo="otra vez", raiz=inicializado)


def test_catalogo_estados_alias_y_reutilizacion(inicializado):
    catalogo = leer(inicializado, "catalog.json")
    modelos = {m["run_id"]: m for m in catalogo["modelos"]}
    assert modelos["m1-c3-seed0"]["estado"] == "recomendado"
    assert modelos["m1-c3-seed0"]["alias"] == ["recomendado:m1", "anterior:produccion"]
    assert modelos["m1b-i1-seed1-best"]["alias"] == ["recomendado:m1b", "servido:produccion"]
    assert modelos["m1-c4-seed1"]["estado"] == "rechazado"
    assert modelos["m1o-e4l-seed0"]["evaluable_con_api"] is False
    assert R.publicar_catalogo(inicializado)["reutilizado"] is True


def test_rollback_de_produccion_ida_y_vuelta(inicializado):
    inicial = leer(inicializado, "catalog.json")
    R.rollback("produccion", motivo="ida", autor="test", raiz=inicializado)
    assert leer(inicializado, "catalog.json")["produccion"] == {"actual": "m1-c3-seed0",
                                                                "anterior": "m1b-i1-seed1-best"}
    R.rollback("produccion", motivo="vuelta", autor="test", raiz=inicializado)
    final = leer(inicializado, "catalog.json")
    assert final["produccion"] == inicial["produccion"] and final["modelos"] == inicial["modelos"]
    historial = leer(inicializado, "aliases.json")["historial"]
    assert [(e["version"], e["accion"]) for e in historial] == [(1, "inicializar"), (2, "rollback"), (3, "rollback")]


def test_rollback_verifica_el_hash_antes_de_mover(inicializado):
    (inicializado / "models/m1-c3-seed0/model.zip").write_bytes(b"alterado")
    with pytest.raises(R.RegistroError, match="no coincide"):
        R.rollback("produccion", motivo="x", raiz=inicializado)
    assert leer(inicializado, "aliases.json")["version"] == 1


def test_promover_mueve_actual_a_anterior_y_degrada_el_estado(inicializado):
    R.promover("m1-c3-seed1", motivo="pre-registro de prueba", autor="test", raiz=inicializado)
    assert leer(inicializado, "aliases.json")["ranuras"]["m1"] == {"actual": "m1-c3-seed1",
                                                                   "anterior": "m1-c3-seed0"}
    modelos = {m["run_id"]: m for m in leer(inicializado, "catalog.json")["modelos"]}
    assert modelos["m1-c3-seed1"]["estado"] == "recomendado"
    assert modelos["m1-c3-seed0"]["estado"] == "candidato"
    assert modelos["m1-c3-seed0"]["estado_manifiesto"] == "recomendado"


@pytest.mark.parametrize("run, kwargs, mensaje", [
    ("m1-c4-seed1", {}, "rechazado"),
    ("m1-c3-seed0", {"ranura": "m1b"}, "es del nivel m1"),
    ("m1o-e4l-seed0", {"ranura": "produccion"}, "warehouse-v5"),
    ("m1-c3-seed1", {"motivo": "  "}, "motivo obligatorio"),
])
def test_promover_rechaza(inicializado, run, kwargs, mensaje):
    with pytest.raises(R.RegistroError, match=mensaje):
        R.promover(run, **{"motivo": "x", **kwargs}, raiz=inicializado)
    assert leer(inicializado, "aliases.json")["version"] == 1


def test_promover_el_actual_no_crea_evento(inicializado):
    assert R.promover("m1-c3-seed0", motivo="x", raiz=inicializado)["version"] == 1


def test_rollback_sin_anterior(inicializado):
    with pytest.raises(R.RegistroError, match="no tiene versión anterior"):
        R.rollback("m1", motivo="x", raiz=inicializado)


def test_registro_del_repo_es_valido_y_el_catalogo_esta_al_dia():
    """manifests/ del repositorio: todo manifiesto salvo el legado cumple el esquema, y catalog.json es
    exactamente lo que se deriva de manifiestos + aliases.json (si falla: python -m pipelines.registry catalogo)."""
    _, excluidos = R.listar_manifiestos(REPO)
    assert [e["archivo"] for e in excluidos] == ["manifests/experiment-001.json"]
    publicado = json.loads((REPO / "manifests/catalog.json").read_text())
    assert publicado["contenido_sha256"] == R.construir_catalogo(REPO)["contenido_sha256"]
