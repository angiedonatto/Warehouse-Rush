"""El run de MLflow cae en el experimento pedido aunque otro proceso lo haya creado antes o a la vez."""
from concurrent.futures import ThreadPoolExecutor

import pytest

mlflow = pytest.importorskip("mlflow")

from pipelines.tracking import experiment_id, mlflow_run  # noqa: E402


@pytest.fixture
def tracking(tmp_path, monkeypatch):
    uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    mlflow.set_tracking_uri(uri)
    return mlflow.tracking.MlflowClient()


def test_experiment_id_is_stable_under_concurrent_creation(tracking):
    with ThreadPoolExecutor(4) as pool:
        ids = list(pool.map(lambda _: experiment_id("warehouse-prueba"), range(4)))
    assert len(set(ids)) == 1
    assert tracking.get_experiment_by_name("warehouse-prueba").experiment_id == ids[0]


def test_mlflow_run_lands_in_the_named_experiment(tracking):
    experiment_id("warehouse-prueba")  # ya existe, como cuando otro run la creó primero
    with mlflow_run(experiment="warehouse-prueba", run_name="r", config={"a": 1}, tags={}) as run:
        pass
    assert tracking.get_experiment(run.info.experiment_id).name == "warehouse-prueba"


def test_tracking_uri_requires_a_server_unless_local_is_explicit(monkeypatch):
    """Sin MLFLOW_TRACKING_URI no se entrena a un sqlite local por accidente."""
    from pipelines.tracking import tracking_uri

    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.delenv("MLFLOW_PERMITIR_LOCAL", raising=False)
    with pytest.raises(RuntimeError, match="MLFLOW_TRACKING_URI"):
        tracking_uri()
    monkeypatch.setenv("MLFLOW_PERMITIR_LOCAL", "1")
    assert tracking_uri() == "sqlite:///mlflow.db"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "https://dagshub.com/o/r.mlflow")
    assert tracking_uri() == "https://dagshub.com/o/r.mlflow"
