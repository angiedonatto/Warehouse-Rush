"""Registra en el Model Registry de MLflow los modelos `recomendado` de manifests/.

Un modelo registrado por nivel (`warehouse-<level_id>`); cada manifiesto recomendado es una versión
con tags (estado, model_sha256, manifiesto, run, suite, test final) y el alias `recomendado`.
Si el peso del manifiesto no es un artefacto del run (p. ej. el mejor checkpoint), se sube a
`modelo_<sufijo>/` del mismo run tras comprobar su SHA-256.

Idempotente: una versión con el mismo `model_sha256` no se vuelve a crear. Nunca sobrescribe:
un modelo nuevo es una versión nueva.

Uso: set -a; source .env; set +a; python -m pipelines.registrar_modelos
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mlflow.tracking import MlflowClient

from pipelines.tracking import sha256_file, tracking_uri


def artefacto_del_modelo(client: MlflowClient, run_id: str, manifest: dict, nombre: str) -> str:
    """Ruta de artefacto (dentro del run) que contiene exactamente el peso del manifiesto."""
    local = Path(manifest["model_uri"])
    if sha256_file(local) != manifest["model_sha256"]:
        raise SystemExit(f"{nombre}: {local} no coincide con model_sha256 del manifiesto")
    for carpeta in ("modelo", f"modelo_{nombre.rsplit('-', 1)[-1]}"):
        for f in client.list_artifacts(run_id, carpeta):
            if f.path.endswith(".zip"):
                with tempfile.TemporaryDirectory() as tmp:
                    bajado = client.download_artifacts(run_id, f.path, tmp)
                    if sha256_file(bajado) == manifest["model_sha256"]:
                        return carpeta
    carpeta = f"modelo_{nombre.rsplit('-', 1)[-1]}"
    client.log_artifact(run_id, str(local), carpeta)
    return carpeta


def main() -> None:
    import mlflow

    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient()
    for p in sorted(Path("manifests").glob("*.json")):
        if p.name == "schema.json":
            continue
        m = json.loads(p.read_text())
        if m.get("estado") != "recomendado":
            continue
        nombre, registro = p.stem, f"warehouse-{m['level_id']}"
        run_id = m["mlflow_run_id"]
        client.get_run(run_id)  # falla si el manifiesto aún apunta al id local

        try:
            client.get_registered_model(registro)
        except Exception:
            client.create_registered_model(registro, description=f"Modelos del nivel {m['level_id']} (ver manifests/)")
        existentes = client.search_model_versions(f"name='{registro}'")
        previa = next((v for v in existentes if v.tags.get("model_sha256") == m["model_sha256"]), None)
        if previa:
            print(f"{nombre}: ya registrado como {registro} v{previa.version}")
            version = previa.version
        else:
            carpeta = artefacto_del_modelo(client, run_id, m, nombre)
            source = f"{client.get_run(run_id).info.artifact_uri}/{carpeta}"
            v = client.create_model_version(registro, source, run_id=run_id,
                                            description=f"{nombre}: {m.get('run_id', nombre)}")
            version = v.version
            tags = {"estado": "recomendado", "model_sha256": m["model_sha256"], "manifiesto": f"manifests/{p.name}",
                    "modelo": nombre, "environment_version": m["environment_version"],
                    "evaluation_suite_id": m["evaluation_suite_id"], "git_commit": m["git_commit"]}
            if m.get("test_final"):
                tags["test_final"] = json.dumps(m["test_final"], ensure_ascii=False)[:5000]
            for k, val in tags.items():
                client.set_model_version_tag(registro, version, k, str(val))
            print(f"{nombre}: registrado como {registro} v{version} (artefacto {carpeta}/)")
        try:
            client.set_registered_model_alias(registro, "recomendado", version)
        except Exception as exc:  # algunos servidores no soportan alias; el tag `estado` basta
            print(f"  alias no soportado por el servidor: {type(exc).__name__}")


if __name__ == "__main__":
    main()
