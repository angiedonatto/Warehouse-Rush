"""Registro de modelos (R3): catálogo, promoción, rollback y verificación de SHA-256.

Fuente de verdad: los manifiestos de `manifests/<run_id>.json` (inmutables) y el archivo de alias
`manifests/aliases.json`. MLflow no se consulta, así el catálogo se reconstruye sin el historial de runs.

- Manifiesto: identidad y evidencia de un modelo (hashes, procedencia, evaluación, decisión al registrarlo).
  No se edita para promover: una promoción o un rollback solo mueve alias.
- Alias: por cada «ranura» (un nivel, p. ej. `m1`, `m1b`, o `produccion` = el modelo que sirve la API)
  guardan `actual` y `anterior`, más un historial de eventos que solo crece.
- Catálogo `manifests/catalog.json`: derivado de manifiestos + alias; es lo que leen la API y la web.
  Si su contenido no cambia, no se reescribe (reejecutar reutiliza el artefacto).

Uso:
  python -m pipelines.registry estado
  python -m pipelines.registry catalogo
  python -m pipelines.registry verificar <run_id> [--descargar]
  python -m pipelines.registry inicializar --produccion <run_id> [--anterior <run_id>] --motivo "..."
  python -m pipelines.registry promover <run_id> [--ranura m1|m1b|produccion] --motivo "..."
  python -m pipelines.registry rollback <ranura> --motivo "..."
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from pipelines.tracking import canonical_json, git_info, sha256_file

RAIZ = Path(__file__).resolve().parents[1]
PRODUCCION = "produccion"
NO_PROMOVIBLES = ("rechazado", "fallido", "interrumpido")
ARCHIVOS_NO_MANIFIESTO = ("schema.json", "catalog.json", "aliases.json")
CATALOGO_SCHEMA_VERSION = 1


class RegistroError(RuntimeError):
    """Operación del registro rechazada (manifiesto inválido, hash distinto, alias inexistente...)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rutas(raiz: Path) -> dict:
    manifests = Path(raiz) / "manifests"
    return {"raiz": Path(raiz), "manifests": manifests, "schema": manifests / "schema.json",
            "catalogo": manifests / "catalog.json", "aliases": manifests / "aliases.json"}


def _escribir_json(path: Path, data) -> None:
    """Escritura atómica: o queda el archivo nuevo completo o el anterior intacto."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _autor(autor: str | None) -> str:
    if autor:
        return autor
    nombre = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True).stdout.strip()
    return nombre or "desconocido"


# --- Manifiestos -----------------------------------------------------------------------------------

def errores_manifiesto(data: dict, raiz: Path = RAIZ) -> list[str]:
    """Errores de esquema (manifests/schema.json) de un manifiesto; lista vacía si es válido."""
    from jsonschema import Draft202012Validator

    schema = json.loads(_rutas(raiz)["schema"].read_text())
    return [f"{'/'.join(map(str, e.path)) or '(raíz)'}: {e.message}"
            for e in Draft202012Validator(schema).iter_errors(data)]


def cargar_manifiesto(run_id: str, raiz: Path = RAIZ) -> dict:
    path = _rutas(raiz)["manifests"] / f"{run_id}.json"
    if Path(run_id).name != run_id or not path.is_file():
        raise RegistroError(f"No existe el manifiesto {path}")
    data = json.loads(path.read_text())
    errores = errores_manifiesto(data, raiz)
    if errores:
        raise RegistroError(f"{path.name} no cumple manifests/schema.json: {errores}")
    if data["run_id"] != run_id:
        raise RegistroError(f"{path.name}: run_id '{data['run_id']}' no coincide con el nombre del archivo")
    return data


def listar_manifiestos(raiz: Path = RAIZ) -> tuple[dict[str, dict], list[dict]]:
    """(manifiestos válidos por run_id, excluidos con motivo). Un manifiesto legado o inválido no
    rompe el catálogo: queda en `excluidos` con su error, visible para quien lo revise."""
    validos, excluidos = {}, []
    for path in sorted(_rutas(raiz)["manifests"].glob("*.json")):
        if path.name in ARCHIVOS_NO_MANIFIESTO:
            continue
        try:
            data = cargar_manifiesto(path.stem, raiz)
        except (RegistroError, json.JSONDecodeError) as exc:
            excluidos.append({"archivo": f"manifests/{path.name}", "motivo": str(exc)[:300]})
            continue
        validos[data["run_id"]] = data
    return validos, excluidos


# --- Verificación de pesos -------------------------------------------------------------------------

def verificar_modelo(run_id: str, *, descargar: bool = False, raiz: Path = RAIZ) -> dict:
    """Compara el SHA-256 del archivo en `model_uri` con el del manifiesto.

    Con `descargar=True`, si el archivo falta lo trae con `dvc pull <weights_dvc>` antes de comparar.
    Devuelve el detalle; `ok` solo es True si el archivo existe y el hash coincide.
    """
    manifest = cargar_manifiesto(run_id, raiz)
    path = Path(raiz) / manifest["model_uri"]
    resultado = {"run_id": run_id, "model_uri": manifest["model_uri"], "esperado": manifest["model_sha256"],
                 "real": None, "presente": path.is_file(), "descargado": False, "ok": False}
    if not path.is_file() and descargar:
        objetivo = manifest.get("weights_dvc")
        if not objetivo:
            resultado["error"] = "el manifiesto no tiene weights_dvc: no se puede descargar"
            return resultado
        proc = subprocess.run([sys.executable, "-m", "dvc", "pull", objetivo], cwd=raiz,
                              capture_output=True, text=True)
        resultado["descargado"] = proc.returncode == 0
        if proc.returncode != 0:
            resultado["error"] = f"dvc pull {objetivo} falló: {(proc.stderr or proc.stdout).strip()[-300:]}"
            return resultado
        resultado["presente"] = path.is_file()
    if resultado["presente"]:
        resultado["real"] = sha256_file(path)
        resultado["ok"] = resultado["real"] == resultado["esperado"]
        if not resultado["ok"]:
            resultado["error"] = "el SHA-256 del archivo no coincide con el manifiesto"
    else:
        resultado.setdefault("error", "el archivo del modelo no está en disco (usa descargar=True / dvc pull)")
    return resultado


def _exigir_verificado(run_id: str, raiz: Path) -> dict:
    resultado = verificar_modelo(run_id, descargar=True, raiz=raiz)
    if not resultado["ok"]:
        raise RegistroError(f"{run_id}: {resultado.get('error')} ({resultado})")
    return resultado


# --- Alias -----------------------------------------------------------------------------------------

def cargar_aliases(raiz: Path = RAIZ) -> dict:
    path = _rutas(raiz)["aliases"]
    if not path.is_file():
        raise RegistroError(f"No existe {path}; créalo con `python -m pipelines.registry inicializar`")
    return json.loads(path.read_text())


def inicializar_aliases(*, produccion: str, anterior_produccion: str | None = None, motivo: str,
                        autor: str | None = None, raiz: Path = RAIZ) -> dict:
    """Crea aliases.json una sola vez a partir de los manifiestos: en cada nivel, `actual` es el
    manifiesto con estado `recomendado` (debe haber como mucho uno por nivel). La ranura de producción
    se declara explícitamente. Si el archivo ya existe, se rechaza: nunca se sobrescribe."""
    rutas = _rutas(raiz)
    if rutas["aliases"].exists():
        raise RegistroError(f"{rutas['aliases']} ya existe; usa promover/rollback")
    if not motivo.strip():
        raise RegistroError("motivo obligatorio")
    manifiestos, _ = listar_manifiestos(raiz)
    ranuras: dict[str, dict] = {}
    for run_id, m in sorted(manifiestos.items()):
        if m.get("estado") != "recomendado":
            continue
        nivel = m["level_id"]
        if nivel in ranuras:
            raise RegistroError(f"Hay dos manifiestos recomendados para {nivel}: "
                                f"{ranuras[nivel]['actual']} y {run_id}")
        ranuras[nivel] = {"actual": run_id, "anterior": None}
    for run_id in filter(None, (produccion, anterior_produccion)):
        _validar_para_produccion(manifiestos, run_id)
        _exigir_verificado(run_id, raiz)
    ranuras[PRODUCCION] = {"actual": produccion, "anterior": anterior_produccion}
    aliases = {"schema_version": 1, "version": 1, "actualizado_en": _ahora(), "ranuras": ranuras,
               "historial": [{"version": 1, "fecha": _ahora(), "autor": _autor(autor), "accion": "inicializar",
                              "ranuras": json.loads(json.dumps(ranuras)), "motivo": motivo.strip()}]}
    _escribir_json(rutas["aliases"], aliases)
    publicar_catalogo(raiz)
    return aliases


def _validar_para_produccion(manifiestos: dict, run_id: str) -> None:
    from envs import ENV_VERSION

    if run_id not in manifiestos:
        raise RegistroError(f"{run_id}: sin manifiesto válido")
    version = manifiestos[run_id]["environment_version"]
    if version != ENV_VERSION:
        raise RegistroError(f"{run_id} es de {version} y el código servido es {ENV_VERSION}: "
                            "la API no puede evaluarlo con su ambiente compatible")


def _registrar_evento(aliases: dict, evento: dict, raiz: Path) -> dict:
    aliases["version"] += 1
    aliases["actualizado_en"] = _ahora()
    aliases["historial"].append({"version": aliases["version"], "fecha": aliases["actualizado_en"], **evento})
    _escribir_json(_rutas(raiz)["aliases"], aliases)
    publicar_catalogo(raiz)
    return aliases


def promover(run_id: str, *, motivo: str, ranura: str | None = None, autor: str | None = None,
             raiz: Path = RAIZ) -> dict:
    """Mueve `actual` de la ranura a `run_id` y deja el anterior en `anterior`.

    Exige: manifiesto válido, estado no rechazado/fallido/interrumpido, SHA-256 verificado (descarga con
    DVC si falta), nivel igual a la ranura (o ambiente compatible si la ranura es producción) y un motivo
    (p. ej. la referencia al pre-registro). Si ya es el actual, no hace nada.
    """
    if not motivo.strip():
        raise RegistroError("motivo obligatorio (cita el pre-registro o la evidencia)")
    manifest = cargar_manifiesto(run_id, raiz)
    ranura = ranura or manifest["level_id"]
    if manifest.get("estado") in NO_PROMOVIBLES:
        raise RegistroError(f"{run_id} está {manifest['estado']}: no se promueve; registra una versión nueva")
    if ranura == PRODUCCION:
        _validar_para_produccion({run_id: manifest}, run_id)
    elif ranura != manifest["level_id"]:
        raise RegistroError(f"{run_id} es del nivel {manifest['level_id']}, no de {ranura}")
    aliases = cargar_aliases(raiz)
    actual = aliases["ranuras"].get(ranura, {}).get("actual")
    if actual == run_id:
        return aliases
    verificado = _exigir_verificado(run_id, raiz)
    aliases["ranuras"][ranura] = {"actual": run_id, "anterior": actual}
    return _registrar_evento(aliases, {"autor": _autor(autor), "accion": "promover", "ranura": ranura,
                                       "de": actual, "a": run_id, "model_sha256": verificado["real"],
                                       "motivo": motivo.strip()}, raiz)


def rollback(ranura: str, *, motivo: str, autor: str | None = None, raiz: Path = RAIZ) -> dict:
    """Intercambia `actual` y `anterior` de la ranura (repetirlo vuelve al estado inicial).
    Verifica antes el SHA-256 del modelo que pasa a ser actual."""
    if not motivo.strip():
        raise RegistroError("motivo obligatorio")
    aliases = cargar_aliases(raiz)
    if ranura not in aliases["ranuras"]:
        raise RegistroError(f"La ranura {ranura} no existe; hay: {sorted(aliases['ranuras'])}")
    actual, anterior = aliases["ranuras"][ranura]["actual"], aliases["ranuras"][ranura]["anterior"]
    if not anterior:
        raise RegistroError(f"La ranura {ranura} no tiene versión anterior a la que volver")
    if ranura == PRODUCCION:
        _validar_para_produccion(listar_manifiestos(raiz)[0], anterior)
    verificado = _exigir_verificado(anterior, raiz)
    aliases["ranuras"][ranura] = {"actual": anterior, "anterior": actual}
    return _registrar_evento(aliases, {"autor": _autor(autor), "accion": "rollback", "ranura": ranura,
                                       "de": actual, "a": anterior, "model_sha256": verificado["real"],
                                       "motivo": motivo.strip()}, raiz)


# --- Catálogo --------------------------------------------------------------------------------------

def _resumen_evaluacion(manifest: dict) -> dict | None:
    evaluacion = manifest.get("evaluation")
    if not evaluacion:
        return None
    claves = ("success_rate", "mean_collisions", "mean_invalid_interactions", "mean_deliveries", "mean_steps")

    def ppo(bloque):
        datos = (bloque or {}).get("ppo")
        return {k: datos.get(k) for k in claves} if datos else None

    escenarios = evaluacion.get("by_scenario")
    resumen = {"suite": evaluacion.get("suite"), "episodios": evaluacion.get("episodes"),
               "determinista": evaluacion.get("deterministic")}
    if escenarios:
        resumen["por_escenario"] = {nombre: ppo(bloque) for nombre, bloque in escenarios.items()}
    else:
        resumen["ppo"] = ppo(evaluacion.get("policies"))
    return resumen


def _entrada(manifest: dict, etiquetas: list[str], estado_catalogo: str, version_actual: str) -> dict:
    test_final = manifest.get("test_final")
    return {
        "run_id": manifest["run_id"], "level_id": manifest["level_id"],
        "estado": estado_catalogo, "estado_manifiesto": manifest.get("estado", "candidato"),
        "alias": etiquetas,
        "environment_version": manifest["environment_version"], "runtime_ref": manifest["runtime_ref"],
        "evaluable_con_api": manifest["environment_version"] == version_actual,
        "seed": manifest["seed"], "parent_run_id": manifest["parent_run_id"],
        "git_commit": manifest["git_commit"], "config_sha256": manifest["config_sha256"],
        "config_uri": manifest.get("config_uri"),
        "model_uri": manifest["model_uri"], "model_sha256": manifest["model_sha256"],
        "normalization_uri": manifest["normalization_uri"], "weights_dvc": manifest.get("weights_dvc"),
        "evaluation_suite_id": manifest["evaluation_suite_id"], "results_uri": manifest.get("results_uri"),
        "budget_steps": manifest.get("budget_steps"), "budget_minutes": manifest.get("budget_minutes"),
        "algorithm": manifest.get("algorithm"), "mlflow_run_id": manifest.get("mlflow_run_id"),
        "created_at": manifest.get("created_at"), "author": manifest.get("author"),
        "decision_reason": manifest.get("decision_reason"),
        "evaluacion": _resumen_evaluacion(manifest),
        "test_final": ({"suite": test_final.get("suite"), "met": test_final.get("met"),
                        "criterion": test_final.get("criterion")} if test_final else None),
        "manifest_uri": f"manifests/{manifest['run_id']}.json",
    }


def construir_catalogo(raiz: Path = RAIZ) -> dict:
    """Catálogo derivado de manifiestos + alias (sin escribirlo).

    `estado` del catálogo: `recomendado` si el modelo es el actual de la ranura de su nivel; si su
    manifiesto dice `recomendado` pero ya no lo es (lo reemplazó una promoción), pasa a `candidato`
    y el manifiesto conserva el registro original en `estado_manifiesto`. Los demás estados se copian.
    """
    from envs import ENV_VERSION

    manifiestos, excluidos = listar_manifiestos(raiz)
    aliases = cargar_aliases(raiz)
    ranuras = aliases["ranuras"]
    for ranura, valor in ranuras.items():
        for clave in ("actual", "anterior"):
            if valor.get(clave) and valor[clave] not in manifiestos:
                raise RegistroError(f"aliases.json: {ranura}.{clave} = {valor[clave]} no tiene manifiesto válido")
    etiquetas: dict[str, list[str]] = {}
    for ranura, valor in sorted(ranuras.items()):
        for clave, nombre in (("actual", "recomendado"), ("anterior", "anterior")):
            if valor.get(clave):
                nombre = "servido" if ranura == PRODUCCION and clave == "actual" else nombre
                etiquetas.setdefault(valor[clave], []).append(f"{nombre}:{ranura}")
    modelos = []
    for run_id, m in sorted(manifiestos.items()):
        estado = m.get("estado", "candidato")
        es_actual = ranuras.get(m["level_id"], {}).get("actual") == run_id
        if es_actual:
            estado = "recomendado"
        elif estado == "recomendado":
            estado = "candidato"
        modelos.append(_entrada(m, etiquetas.get(run_id, []), estado, ENV_VERSION))
    contenido = {
        "schema_version": CATALOGO_SCHEMA_VERSION, "environment_version_servida": ENV_VERSION,
        "aliases_version": aliases["version"],
        "produccion": ranuras.get(PRODUCCION),
        "niveles": {r: v for r, v in sorted(ranuras.items()) if r != PRODUCCION},
        "modelos": modelos, "excluidos": excluidos,
    }
    from hashlib import sha256

    contenido["contenido_sha256"] = sha256(canonical_json(contenido).encode()).hexdigest()
    return contenido


def publicar_catalogo(raiz: Path = RAIZ) -> dict:
    """Escribe manifests/catalog.json si su contenido cambió; si no, reutiliza el existente.
    Devuelve el catálogo con `reutilizado` (no se guarda en el archivo)."""
    path = _rutas(raiz)["catalogo"]
    catalogo = construir_catalogo(raiz)
    if path.is_file():
        previo = json.loads(path.read_text())
        if previo.get("contenido_sha256") == catalogo["contenido_sha256"]:
            return {**previo, "reutilizado": True}
    git = git_info()
    catalogo = {**catalogo, "generado_en": _ahora(), "git_commit": git["git_commit"], "git_dirty": git["git_dirty"]}
    _escribir_json(path, catalogo)
    return {**catalogo, "reutilizado": False}


def modelo_servido(raiz: Path = RAIZ) -> dict:
    """Manifiesto del modelo que debe servir la API (alias `produccion.actual`)."""
    return cargar_manifiesto(cargar_aliases(raiz)["ranuras"][PRODUCCION]["actual"], raiz)


# --- CLI -------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Registro de modelos: catálogo, promoción y rollback")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estado", help="ranuras actuales y últimos eventos")
    sub.add_parser("catalogo", help="regenera manifests/catalog.json si cambió")
    p = sub.add_parser("verificar", help="SHA-256 del modelo frente al manifiesto")
    p.add_argument("run_id")
    p.add_argument("--descargar", action="store_true", help="dvc pull si el archivo falta")
    p = sub.add_parser("inicializar", help="crea manifests/aliases.json (una sola vez)")
    p.add_argument("--produccion", required=True)
    p.add_argument("--anterior")
    p.add_argument("--motivo", required=True)
    p.add_argument("--autor")
    p = sub.add_parser("promover")
    p.add_argument("run_id")
    p.add_argument("--ranura")
    p.add_argument("--motivo", required=True)
    p.add_argument("--autor")
    p = sub.add_parser("rollback")
    p.add_argument("ranura")
    p.add_argument("--motivo", required=True)
    p.add_argument("--autor")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "estado":
            aliases = cargar_aliases()
            salida = {"version": aliases["version"], "ranuras": aliases["ranuras"],
                      "ultimos_eventos": aliases["historial"][-5:]}
        elif args.cmd == "catalogo":
            cat = publicar_catalogo()
            salida = {k: cat[k] for k in ("contenido_sha256", "reutilizado", "aliases_version", "produccion")}
            salida.update(modelos=len(cat["modelos"]), excluidos=[e["archivo"] for e in cat["excluidos"]])
        elif args.cmd == "verificar":
            salida = verificar_modelo(args.run_id, descargar=args.descargar)
        elif args.cmd == "inicializar":
            salida = inicializar_aliases(produccion=args.produccion, anterior_produccion=args.anterior,
                                         motivo=args.motivo, autor=args.autor)["ranuras"]
        elif args.cmd == "promover":
            salida = promover(args.run_id, motivo=args.motivo, ranura=args.ranura, autor=args.autor)["ranuras"]
        else:
            salida = rollback(args.ranura, motivo=args.motivo, autor=args.autor)["ranuras"]
    except RegistroError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    return 0 if args.cmd != "verificar" or salida["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
