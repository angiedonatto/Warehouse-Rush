"""Entrenamiento PPO reproducible en CPU y artefactos locales."""

from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import time

from warehouse_rush import __version__
from warehouse_rush.env import WarehouseRushEnv


def default_model(orders=1, seed=42) -> Path:
    return Path(f"artifacts/models/ppo_orders{orders}_seed{seed}.zip")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def train_ppo(*, timesteps=20_000, seed=42, orders=1, blocked=False, layout_path=None,
              n_steps=500, batch_size=100, run_name=None) -> dict:
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor

    if timesteps < 1 or n_steps < 2 or batch_size < 2 or n_steps % batch_size:
        raise ValueError("timesteps > 0; batch_size >= 2 debe dividir n_steps >= 2")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    name = run_name or f"ppo_o{orders}_s{seed}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    if Path(name).name != name or name in (".", ".."):
        raise ValueError("run_name debe ser un nombre simple")
    run_dir = Path("results/training") / name
    model_dir = Path("artifacts/models") / name
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    env = WarehouseRushEnv(orders, blocked, layout_path)
    eval_env = Monitor(WarehouseRushEnv(orders, blocked, layout_path))
    eval_env.reset(seed=20_000)
    hyperparameters = dict(learning_rate=3e-4, n_steps=n_steps, batch_size=batch_size,
                           n_epochs=10, gamma=0.99, gae_lambda=0.95, clip_range=0.2,
                           ent_coef=0.01, vf_coef=0.5, max_grad_norm=0.5,
                           policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]}})
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    metadata = {
        "status": "running", "algorithm": "PPO", "policy": "MlpPolicy",
        "environment_version": __version__, "seed": seed, "orders": orders,
        "blocked": blocked, "requested_timesteps": timesteps,
        "hyperparameters": hyperparameters, "device": "cpu", "torch_threads": 1,
        "scenario": env.layout.data, "layout_sha256": env.layout.digest,
        "simulation": asdict(env.config), "rewards": asdict(env.reward_config),
        "python": platform.python_version(), "platform": platform.platform(),
        "versions": {p: version(p) for p in ("numpy", "gymnasium", "torch", "stable-baselines3", "matplotlib")},
        "git_revision": revision.stdout.strip(), "git_dirty": bool(dirty.stdout.strip()),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "periodic_eval_seed": 20_000, "periodic_eval_episodes": 5,
    }
    write_json(run_dir / "metadata.json", metadata)
    monitor = Monitor(env, str(run_dir / "episodes"),
                      info_keywords=("success", "deliveries", "collisions", "end_reason"))
    started = time.perf_counter()
    try:
        model = PPO("MlpPolicy", monitor, seed=seed, device="cpu", verbose=0, **hyperparameters)
        model.set_logger(configure(str(run_dir), ["csv"]))
        callbacks = [
            CheckpointCallback(save_freq=5000, save_path=str(model_dir / "checkpoints"), name_prefix="ppo", verbose=0),
            EvalCallback(eval_env, n_eval_episodes=5, eval_freq=5000,
                         log_path=str(run_dir / "periodic_eval"),
                         best_model_save_path=str(model_dir / "best"), deterministic=True, verbose=0),
        ]
        model.learn(total_timesteps=timesteps, callback=callbacks, log_interval=1)
        duration = time.perf_counter() - started
        final_path = model_dir / "model.zip"
        model.save(final_path)
        alias = default_model(orders, seed)
        shutil.copy2(final_path, alias)
        metadata.update(status="completed", effective_timesteps=model.num_timesteps,
                        duration_seconds=duration, model_path=str(final_path), model_alias=str(alias),
                        completed_at_utc=datetime.now(timezone.utc).isoformat())
        write_json(run_dir / "metadata.json", metadata)
        write_json(alias.with_suffix(".json"), metadata)
        summarize_training(run_dir)
        plot_training_curve(run_dir / "episodes.monitor.csv", run_dir / "training_curve.png")
        return metadata
    except Exception as exc:
        metadata.update(status="failed", duration_seconds=time.perf_counter() - started,
                        error=f"{type(exc).__name__}: {exc}")
        write_json(run_dir / "metadata.json", metadata)
        raise
    finally:
        monitor.close()
        eval_env.close()


def summarize_training(run_dir: Path) -> dict:
    """Exportar también evaluaciones periódicas a JSON y resumir Monitor."""
    import csv
    import numpy as np

    with (run_dir / "episodes.monitor.csv").open() as handle:
        next(handle)
        rows = list(csv.DictReader(handle))
    rewards = [float(row["r"]) for row in rows]
    summary = {
        "completed_training_episodes": len(rows),
        "training_successes": sum(row["success"] == "True" for row in rows),
        "first_10_episode_mean_reward": float(np.mean(rewards[:10])) if rows else None,
        "last_10_episode_mean_reward": float(np.mean(rewards[-10:])) if rows else None,
        "mean_episode_length": float(np.mean([int(row["l"]) for row in rows])) if rows else None,
        "periodic_evaluations": {},
    }
    periodic = run_dir / "periodic_eval/evaluations.npz"
    if periodic.is_file():
        with np.load(periodic) as arrays:
            summary["periodic_evaluations"] = {key: arrays[key].tolist() for key in arrays.files}
    write_json(run_dir / "metrics.json", summary)
    return summary


def plot_training_curve(monitor_path: Path, output: Path) -> bool:
    import csv
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    with monitor_path.open() as handle:
        next(handle)  # Cabecera de metadatos de Monitor.
        rows = list(csv.DictReader(handle))
    if len(rows) < 2:
        return False
    steps = np.cumsum([int(row["l"]) for row in rows])
    rewards = np.asarray([float(row["r"]) for row in rows])
    window = min(10, len(rows))
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(steps, rewards, alpha=0.4, label="Retorno por episodio (entrenamiento)")
    ax.plot(steps[window - 1:], np.convolve(rewards, np.ones(window) / window, mode="valid"),
            label=f"Media móvil de {window} episodios")
    ax.set(xlabel="Pasos de entorno acumulados", ylabel="Recompensa", title="Warehouse Rush — PPO")
    ax.legend(fontsize=8)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return True
