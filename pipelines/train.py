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

import gymnasium as gym

from envs import ENV_VERSION, __version__, make_env
from envs.env import WarehouseRushEnv


class StagnationStop(gym.Wrapper):
    """Solo para el ENTRENAMIENTO: trunca el episodio tras `window` pasos sin superar el mejor potencial Phi del episodio.

    Phi (`env.potential()`, v9) es una función del estado y solo se usa para decidir la parada; no entra en la observación.
    Se marca `truncated` (no `terminated`) para que PPO haga bootstrap del valor (SB3 lo trata como límite de tiempo).
    La evaluación (suites, evaluate.py, EvalCallback) usa el ambiente sin envolver y conserva los 400 pasos.
    """

    def __init__(self, env, window: int):
        super().__init__(env)
        if type(window) is not int or window < 1:
            raise ValueError("window debe ser un entero >= 1")
        self.window = window
        self._best, self._since = 0.0, 0

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._best, self._since = self.env.unwrapped.potential(), 0
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        potential = self.env.unwrapped.potential()
        if potential > self._best + 1e-9:
            self._best, self._since = potential, 0
        else:
            self._since += 1
        if not (terminated or truncated) and self._since >= self.window:
            truncated = True
            info = {**info, "end_reason": "stagnation", "stagnation_stop": True}
        return obs, reward, terminated, truncated, info


def default_model(orders=1, seed=42, algo="ppo") -> Path:
    return Path(f"models/{algo}_orders{orders}_seed{seed}.zip")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


# Hiperparámetros por defecto del experimento 001 (dev/angie). Los experimentos del plan
# (configs/experiments/*.yaml) los reemplazan: el código no debe llevar valores a mano.
DEFAULT_PPO = dict(learning_rate=3e-4, n_steps=500, batch_size=100, n_epochs=10, gamma=0.99,
                   gae_lambda=0.95, clip_range=0.2, ent_coef=0.01, vf_coef=0.5, max_grad_norm=0.5,
                   net_arch=[64, 64])


# DQN (alternativa a PPO, misma recompensa y ambiente): acciones Discrete(8), replay buffer y
# exploración epsilon-greedy que no colapsa a una política determinista como PPO en C0-C1c.
DEFAULT_DQN = dict(learning_rate=5e-4, buffer_size=100_000, learning_starts=5_000, batch_size=64,
                   tau=1.0, gamma=0.99, train_freq=4, gradient_steps=1, target_update_interval=1_000,
                   exploration_fraction=0.5, exploration_initial_eps=1.0, exploration_final_eps=0.05,
                   max_grad_norm=10.0, net_arch=[64, 64])


def training_env_blocked(index: int, blocked) -> bool:
    """Si el ambiente de entrenamiento `index` tiene el paso cerrable cerrado.

    `blocked` viene del nivel (configs/niveles.yaml): false, true o 'mixto'. 'mixto' (nivel m1b,
    incidente N3) cierra el paso en los ambientes pares y lo deja abierto en los impares, para
    aprender la ruta alternativa sin olvidar el mapa normal.
    """
    if blocked == "mixto":
        return index % 2 == 0
    if blocked in (False, True):
        return bool(blocked)
    raise ValueError("blocked debe ser false, true o 'mixto'")


def train_ppo(*, timesteps=20_000, seed=42, orders=1, blocked=False, layout_path=None,
              n_steps=None, batch_size=None, run_name=None, ppo=None, n_envs=1,
              eval_every=5_000, eval_episodes=5, parent_model=None, algo="ppo",
              reward_overrides=None, stagnation_window=None) -> dict:
    """Entrena PPO (referencia del plan) o DQN con el mismo ambiente, recompensa y trazabilidad."""
    import torch
    from stable_baselines3 import DQN, PPO
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.monitor import Monitor

    if algo not in ("ppo", "dqn"):
        raise ValueError("algo debe ser ppo o dqn")
    training_env_blocked(0, blocked)  # valida antes de crear carpetas
    params = {**(DEFAULT_PPO if algo == "ppo" else DEFAULT_DQN), **(ppo or {})}
    if batch_size is not None:
        params["batch_size"] = batch_size
    batch_size = params["batch_size"]
    if algo == "ppo":
        if n_steps is not None:
            params["n_steps"] = n_steps
        n_steps = params["n_steps"]
        if timesteps < 1 or n_envs < 1 or n_steps < 2 or batch_size < 2 or (n_steps * n_envs) % batch_size:
            raise ValueError("timesteps > 0; batch_size >= 2 debe dividir n_steps * n_envs")
    elif timesteps < 1 or n_envs < 1 or batch_size < 2:
        raise ValueError("timesteps > 0, n_envs >= 1 y batch_size >= 2")
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    name = run_name or f"ppo_o{orders}_s{seed}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    if Path(name).name != name or name in (".", ".."):
        raise ValueError("run_name debe ser un nombre simple")
    run_dir = Path("docs/resultados/training") / name
    model_dir = Path("models") / name
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    blocked_eval = training_env_blocked(0, blocked)  # 'mixto': la evaluación periódica usa el paso cerrado
    env = make_env(blocked_eval, layout_path, orders, reward_overrides)  # referencia para metadatos
    eval_env = Monitor(make_env(blocked_eval, layout_path, orders, reward_overrides))
    eval_env.reset(seed=20_000)
    net_arch = params.pop("net_arch")
    arch = {"pi": list(net_arch), "vf": list(net_arch)} if algo == "ppo" else list(net_arch)
    hyperparameters = {**params, "policy_kwargs": {"net_arch": arch}}
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    metadata = {
        "status": "running", "algorithm": algo.upper(), "policy": "MlpPolicy",
        "environment_version": ENV_VERSION, "environment_sheet_version": __version__, "seed": seed, "orders": orders,
        "blocked": blocked, "requested_timesteps": timesteps,
        "hyperparameters": hyperparameters, "n_envs": n_envs, "parent_model": str(parent_model) if parent_model else None, "device": "cpu", "torch_threads": 1,
        "scenario": env.layout.data, "layout_sha256": env.layout.digest,
        "simulation": asdict(env.config), "rewards": asdict(env.reward_config),
        "reward_overrides": dict(reward_overrides or {}),
        "layout_path": str(layout_path) if layout_path else None,
        "python": platform.python_version(), "platform": platform.platform(),
        "versions": {p: version(p) for p in ("numpy", "gymnasium", "torch", "stable-baselines3", "matplotlib")},
        "git_revision": revision.stdout.strip(), "git_dirty": bool(dirty.stdout.strip()),
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "stagnation_window": stagnation_window, "periodic_eval_seed": 20_000, "periodic_eval_episodes": eval_episodes, "periodic_eval_every": eval_every,
    }
    write_json(run_dir / "metadata.json", metadata)
    from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor

    def make_train_env(index=0):
        train_env = make_env(training_env_blocked(index, blocked), layout_path, orders, reward_overrides)
        return StagnationStop(train_env, stagnation_window) if stagnation_window else train_env

    vec_env = DummyVecEnv([lambda i=i: make_train_env(i) for i in range(n_envs)])
    monitor = VecMonitor(vec_env, str(run_dir / "episodes"),
                         info_keywords=("success", "deliveries", "collisions", "end_reason"))
    started = time.perf_counter()
    try:
        if algo == "dqn":
            if parent_model:
                raise ValueError("DQN no admite parent_run_id (el replay buffer no se hereda)")
            model = DQN("MlpPolicy", monitor, seed=seed, device="cpu", verbose=0, **hyperparameters)
        elif parent_model:  # continuar desde un checkpoint compatible (parent_run_id)
            model = PPO.load(str(parent_model), env=monitor, device="cpu", seed=seed)
            from stable_baselines3.common.utils import get_schedule_fn

            # Reaplicar los hiperparámetros del config; n_steps queda el del padre (buffer ya creado).
            model.lr_schedule = get_schedule_fn(hyperparameters["learning_rate"])
            model.clip_range = get_schedule_fn(hyperparameters["clip_range"])
            for key in ("gamma", "gae_lambda", "ent_coef", "vf_coef", "max_grad_norm", "n_epochs", "batch_size"):
                setattr(model, key, hyperparameters[key])
        else:
            model = PPO("MlpPolicy", monitor, seed=seed, device="cpu", verbose=0, **hyperparameters)
        model.set_logger(configure(str(run_dir), ["csv"]))
        callbacks = [
            CheckpointCallback(save_freq=max(eval_every // n_envs, 1), save_path=str(model_dir / "checkpoints"), name_prefix="ppo", verbose=0),
            EvalCallback(eval_env, n_eval_episodes=eval_episodes, eval_freq=max(eval_every // n_envs, 1),
                         log_path=str(run_dir / "periodic_eval"),
                         best_model_save_path=str(model_dir / "best"), deterministic=True, verbose=0),
        ]
        model.learn(total_timesteps=timesteps, callback=callbacks, log_interval=1,
                    reset_num_timesteps=not parent_model)
        duration = time.perf_counter() - started
        final_path = model_dir / "model.zip"
        model.save(final_path)
        alias = default_model(orders, seed, algo)
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


# --- Entrenamiento desde configuración del plan (configs/experiments/*.yaml) ---

def load_config(path) -> dict:
    import yaml

    config = yaml.safe_load(Path(path).read_text())
    algo = config.get("algoritmo", "ppo")
    if algo not in ("ppo", "dqn"):
        raise ValueError(f"{path}: algoritmo desconocido '{algo}'")
    for key in ("id", "hipotesis", "nivel", "environment_version", "seed", "presupuesto_pasos", algo):
        if key not in config:
            raise ValueError(f"{path}: falta la clave obligatoria '{key}'")
    if config["environment_version"] != ENV_VERSION:
        raise ValueError(f"El config pide {config['environment_version']} pero el ambiente es {ENV_VERSION}: "
                         "otra versión implica otra familia de modelos")
    from envs import reward_config

    reward_config(config.get("recompensa"))  # valida claves y signos antes de entrenar
    window = config.get("parada_estancamiento")
    if window is not None and (type(window) is not int or window < 1):
        raise ValueError(f"{path}: parada_estancamiento debe ser un entero >= 1 (pasos sin mejorar el potencial)")
    levels = yaml.safe_load(Path("configs/niveles.yaml").read_text())
    if config["nivel"] not in levels:
        raise ValueError(f"nivel desconocido: {config['nivel']}")
    return config


def run_name_for(config: dict) -> str:
    """<nivel>-<hipótesis>-seed<semilla>, p. ej. n1-c0-seed0 (acuerdo del equipo)."""
    return f"{config['nivel']}-{config['id']}-seed{config['seed']}"


def train_from_config(path, *, tipo="candidato", timesteps=None) -> dict:
    """Entrena PPO desde un YAML y registra todo en MLflow (params, tags, config, modelo, estado)."""
    import yaml
    import mlflow

    from pipelines.tracking import mlflow_run, sha256_config, sha256_file

    config = load_config(path)
    levels = yaml.safe_load(Path("configs/niveles.yaml").read_text())
    level = levels[config["nivel"]]
    budget = timesteps or config["presupuesto_pasos"]
    config_hash = sha256_config(config)
    name = run_name_for(config)
    algo = config.get("algoritmo", "ppo")
    ppo = dict(config[algo])
    n_envs = ppo.pop("n_envs", 1)
    evaluation = config.get("evaluacion", {})
    parent = config.get("parent_run_id")
    parent_model = None
    if parent and not str(parent).startswith("<"):
        parent_model = Path("models") / parent / "model.zip"
        if not parent_model.is_file():
            raise FileNotFoundError(f"parent_run_id {parent}: no existe {parent_model}")
    tags = {"nivel": config["nivel"], "hipotesis": config["hipotesis"].strip(), "tipo": tipo,
            "estado": "candidato", "algoritmo": algo, "environment_version": ENV_VERSION, "config_sha256": config_hash,
            "parent_run_id": parent or "none", "config_id": config["id"], "seed": config["seed"],
            "suite_final": evaluation.get("final", ""), "runtime_ref": f"env/{ENV_VERSION}",
            "recompensa": json.dumps(config.get("recompensa") or {}, sort_keys=True),
            "layout": str(config.get("layout") or "default")}
    with mlflow_run(experiment=f"warehouse-{config['nivel']}", run_name=name,
                    config={**config, "presupuesto_efectivo": budget}, tags=tags):
        meta = train_ppo(timesteps=budget, seed=config["seed"], orders=level["orders"],
                         blocked=level["blocked"], run_name=name, ppo=ppo, n_envs=n_envs,
                         eval_every=evaluation.get("cada_pasos", 5_000), parent_model=parent_model, algo=algo,
                         reward_overrides=config.get("recompensa"), layout_path=config.get("layout"),
                         stagnation_window=config.get("parada_estancamiento"))
        model_path = Path(meta["model_path"])
        mlflow.log_artifact(str(model_path), artifact_path="modelo")
        mlflow.set_tags({"model_sha256": sha256_file(model_path), "pasos_reales": meta["effective_timesteps"]})
        mlflow.log_metrics({"minutos_reales": meta["duration_seconds"] / 60})
        run_dir = Path("docs/resultados/training") / name
        for artifact in ("metrics.json", "metadata.json", "training_curve.png", "progress.csv"):
            if (run_dir / artifact).is_file():
                mlflow.log_artifact(str(run_dir / artifact), artifact_path="entrenamiento")
        metrics = json.loads((run_dir / "metrics.json").read_text())
        mlflow.log_metrics({"train/episodios": metrics["completed_training_episodes"],
                            "train/exitos": metrics["training_successes"]})
        meta["mlflow_run_id"] = mlflow.active_run().info.run_id
    return meta


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Entrena PPO desde un YAML de configs/experiments/")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--tipo", default="candidato", choices=("candidato", "referencia"))
    parser.add_argument("--timesteps", type=int, help="Reemplaza el presupuesto (solo pruebas de humo)")
    args = parser.parse_args(argv)
    meta = train_from_config(args.config, tipo=args.tipo, timesteps=args.timesteps)
    print(json.dumps({k: meta[k] for k in ("model_path", "effective_timesteps", "duration_seconds",
                                           "mlflow_run_id")}, indent=2))


if __name__ == "__main__":
    main()
