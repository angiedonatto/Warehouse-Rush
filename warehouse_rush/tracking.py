"""Experiment tracking (MLflow) and model publishing (Hugging Face Hub)."""
import json
from pathlib import Path

import mlflow
from mlflow.entities import Metric

TRACKING_URI = "sqlite:///mlflow.db"
EXPERIMENT = "warehouse-rush"

MODEL_CARD = """---
library_name: gymnasium
tags: [reinforcement-learning, q-learning, gridworld]
---
# Warehouse Rush: grid navigation Q-table

Tabular Q-learning agent for `warehouse_rush.GridEnv` (random obstacles every episode).

- Observation: x, y, blocked flag and visited flag for each neighbour (UP, DOWN, LEFT, RIGHT)
- Actions: UP, DOWN, LEFT, RIGHT
- `qtable.npy` shape: `(size, size, 2, 2, 2, 2, 2, 2, 2, 2, 4)`

## Config
```json
{config}
```
## Final evaluation (greedy, fixed layouts)
```json
{metrics}
```
"""


class Run:
    """Thin wrapper so the training loop doesn't depend on MLflow details."""

    def __init__(self, params, run_name=None):
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT)
        self._ctx = mlflow.start_run(run_name=run_name)
        self.run_id = self._ctx.info.run_id
        self._client = mlflow.MlflowClient()
        self._buf = []
        mlflow.log_params(params)

    def metric(self, key, value, step):
        self._buf.append(Metric(key, float(value), 0, step))

    def flush(self):
        if self._buf:
            self._client.log_batch(self.run_id, metrics=self._buf)
            self._buf = []

    def finish(self, artifacts_dir, final_metrics, stopped_early):
        self.flush()
        mlflow.log_metrics(final_metrics)
        mlflow.set_tag("stopped_early", str(stopped_early))
        mlflow.log_artifacts(str(artifacts_dir), artifact_path="model")
        mlflow.end_run()


def write_model_dir(directory, agent, config, metrics):
    """Save the Q-table + config + model card; this folder is what goes to the Hub."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    agent.save(d / "qtable.npy")
    (d / "config.json").write_text(json.dumps(config, indent=2))
    (d / "README.md").write_text(
        MODEL_CARD.format(config=json.dumps(config, indent=2), metrics=json.dumps(metrics, indent=2))
    )


def push_to_hub(directory, repo_id):
    from huggingface_hub import HfApi

    api = HfApi()  # uses HF_TOKEN or `huggingface-cli login`
    api.create_repo(repo_id, repo_type="model", exist_ok=True)
    info = api.upload_folder(folder_path=str(directory), repo_id=repo_id, repo_type="model")
    print(f"pushed to https://huggingface.co/{repo_id} ({info})")
