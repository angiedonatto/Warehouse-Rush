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
