"""Clonación de comportamiento: imita a la heurística y deja un modelo PPO compatible para continuar con PPO.

Flujo (todo desde un YAML de configs/experiments/, como el resto de runs):
  1. Demostraciones: la heurística (BFS + secuencia SUBIR/CARGAR/BAJAR/DESCARGAR) recorre episodios del nivel. Una parte de
     los episodios inyecta acciones al azar con probabilidad `noise` (estilo DART): el estado cambia pero la etiqueta es
     siempre lo que haría la heurística en ese estado, así el modelo también ve estados fuera de la ruta perfecta.
  2. Pretraining: entropía cruzada de la política (actor) y regresión del valor (crítico) con los retornos descontados
     de la propia trayectoria, con la misma arquitectura que PPO para que `parent_run_id` cargue el modelo.
  3. Se guarda `models/<run>/model.zip` + `docs/resultados/training/<run>/metadata.json` y se registra en MLflow.
El modelo resultante se evalúa solo (política BC) o se usa como `parent_run_id` de un run PPO de ajuste fino.
Las semillas de demostración (40000+) y de validación (50000+) no coinciden con la suite (10000-10049), dev (1000-1009),
la evaluación periódica (20000) ni el diagnóstico estocástico (20000-20049).
"""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from multiprocessing import Pool
from pathlib import Path
import time

import numpy as np

from envs import ENV_VERSION, make_env
from pipelines.baselines import HeuristicPolicy

DEMO_SEED_START = 40_000
VAL_SEED_START = 50_000


def _rollout(args):
    """Un episodio: acciones de la heurística, con ruido opcional; etiquetas = acción de la heurística en cada estado."""
    layout_path, orders, reward_overrides, seed, noise, gamma = args
    env = make_env(layout_path=layout_path, orders=orders, reward_overrides=reward_overrides)
    obs, _ = env.reset(seed=seed)
    expert, rng = HeuristicPolicy(), np.random.default_rng(seed)
    observations, labels, rewards = [], [], []
    done, failed = False, False
    info = {}
    while not done:
        try:
            label = expert.action(obs, env)
        except RuntimeError:        # sin ruta heurística desde un estado perturbado: se corta el episodio
            failed = True
            break
        action = int(rng.integers(env.action_space.n)) if noise and rng.random() < noise else label
        observations.append(obs)
        labels.append(label)
        obs, reward, terminated, truncated, info = env.step(action)
        rewards.append(reward)
        done = terminated or truncated
    returns, running = np.zeros(len(rewards), dtype=np.float32), 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = rewards[index] + gamma * running
        returns[index] = running
    return (np.asarray(observations, dtype=np.float32), np.asarray(labels, dtype=np.int64), returns,
            bool(info.get("success")), failed)


def collect_demos(*, layout_path, orders, reward_overrides, episodes, seed_start, noise, gamma, workers=8):
    """`noise` es una lista de probabilidades; los episodios se reparten por igual entre ellas."""
    jobs = [(layout_path, orders, reward_overrides, seed_start + i, noise[i % len(noise)], gamma) for i in range(episodes)]
    with Pool(workers) as pool:
        results = pool.map(_rollout, jobs, chunksize=4)
    obs = np.concatenate([r[0] for r in results])
    actions = np.concatenate([r[1] for r in results])
    returns = np.concatenate([r[2] for r in results])
    noisy = np.concatenate([np.full(len(r[1]), jobs[i][4] > 0) for i, r in enumerate(results)])
    clean = [r[3] for i, r in enumerate(results) if jobs[i][4] == 0]
    return dict(obs=obs, actions=actions, returns=returns, noisy=noisy,
                expert_clean_success=float(np.mean(clean)) if clean else None,
                cut_episodes=int(sum(r[4] for r in results)), episodes=episodes)


def demos_sha256(demos) -> str:
    digest = sha256()
    for key in ("obs", "actions", "returns"):
        digest.update(np.ascontiguousarray(demos[key]).tobytes())
    return digest.hexdigest()


def pretrain(model, demos, *, epochs, lr, batch_size, seed, validation=None):
    """BC del actor + regresión del crítico sobre un PPO ya construido. Devuelve métricas finales."""
    import torch
    import torch.nn.functional as F

    torch.set_num_threads(1)
    torch.manual_seed(seed)
    policy = model.policy
    optimizer = torch.optim.Adam(policy.parameters(), lr=lr)
    obs = torch.as_tensor(demos["obs"])
    actions = torch.as_tensor(demos["actions"])
    returns = torch.as_tensor(demos["returns"])
    generator = torch.Generator().manual_seed(seed)
    count = len(obs)
    for _ in range(epochs):
        order = torch.randperm(count, generator=generator)
        for start in range(0, count, batch_size):
            index = order[start:start + batch_size]
            distribution = policy.get_distribution(obs[index])
            actor_loss = -distribution.log_prob(actions[index]).mean()
            critic_loss = F.smooth_l1_loss(policy.predict_values(obs[index]).squeeze(-1), returns[index], beta=10.0)
            optimizer.zero_grad()
            (actor_loss + critic_loss).backward()      # actor y crítico son redes separadas: no se pisan
            optimizer.step()
    return evaluate_fit(policy, demos, validation)


def evaluate_fit(policy, demos, validation=None) -> dict:
    import torch

    def block(data):
        with torch.no_grad():
            tensor = torch.as_tensor(data["obs"])
            predicted = policy.get_distribution(tensor).distribution.probs.argmax(dim=1).numpy()
            values = policy.predict_values(tensor).squeeze(-1).numpy()
        hit = predicted == data["actions"]
        returns = data["returns"]
        variance = float(np.var(returns))
        return dict(accuracy=float(hit.mean()),
                    accuracy_clean_states=float(hit[~data["noisy"]].mean()) if (~data["noisy"]).any() else None,
                    accuracy_noisy_states=float(hit[data["noisy"]].mean()) if data["noisy"].any() else None,
                    value_explained_variance=float(1 - np.var(returns - values) / variance) if variance > 0 else None)
    out = {"train": block(demos)}
    if validation is not None:
        out["validation"] = block(validation)
    return out


def run_bc(config_path, *, workers=8) -> dict:
    """Ejecuta una clonación de comportamiento desde un YAML (`bc:` con los parámetros) y registra el run en MLflow."""
    import mlflow
    import torch
    import yaml
    from stable_baselines3 import PPO

    from pipelines.train import load_config, run_name_for, write_json
    from pipelines.tracking import git_info, mlflow_run, sha256_config, sha256_file

    config = load_config(config_path)
    bc = config["bc"]
    levels = yaml.safe_load(Path("configs/niveles.yaml").read_text())
    level = levels[config["nivel"]]
    layout_path, reward_overrides = config.get("layout"), config.get("recompensa") or None
    ppo_params = dict(config["ppo"])
    n_envs = ppo_params.pop("n_envs", 1)
    net_arch = ppo_params.pop("net_arch")
    gamma = ppo_params["gamma"]
    name = run_name_for(config)
    run_dir, model_dir = Path("docs/resultados/training") / name, Path("models") / name
    run_dir.mkdir(parents=True, exist_ok=False)
    model_dir.mkdir(parents=True, exist_ok=False)
    tags = {"nivel": config["nivel"], "hipotesis": config["hipotesis"].strip(), "tipo": "candidato", "estado": "candidato",
            "algoritmo": "ppo+bc", "environment_version": ENV_VERSION, "config_sha256": sha256_config(config),
            "parent_run_id": "none", "config_id": config["id"], "seed": config["seed"],
            "suite_final": config.get("evaluacion", {}).get("final", ""), "runtime_ref": f"env/{ENV_VERSION}",
            "recompensa": json.dumps(config.get("recompensa") or {}, sort_keys=True), "layout": str(layout_path or "default")}
    started = time.perf_counter()
    with mlflow_run(experiment=f"warehouse-{config['nivel']}", run_name=name,
                    config={**config, "presupuesto_efectivo": 0}, tags=tags) as run:
        demos = collect_demos(layout_path=layout_path, orders=level["orders"], reward_overrides=reward_overrides,
                              episodes=bc["episodes"], seed_start=DEMO_SEED_START, noise=bc["noise"], gamma=gamma, workers=workers)
        validation = collect_demos(layout_path=layout_path, orders=level["orders"], reward_overrides=reward_overrides,
                                   episodes=bc["val_episodes"], seed_start=VAL_SEED_START, noise=bc["noise"], gamma=gamma, workers=workers)
        from stable_baselines3.common.vec_env import DummyVecEnv

        torch.use_deterministic_algorithms(True)
        env = DummyVecEnv([lambda: make_env(layout_path=layout_path, orders=level["orders"], reward_overrides=reward_overrides)
                           for _ in range(n_envs)])
        hyper = {**ppo_params, "policy_kwargs": {"net_arch": {"pi": list(net_arch), "vf": list(net_arch)}}}
        model = PPO("MlpPolicy", env, seed=config["seed"], device="cpu", verbose=0, **hyper)
        fit = pretrain(model, demos, epochs=bc["epochs"], lr=bc["lr"], batch_size=bc["batch_size"],
                       seed=config["seed"], validation=validation)
        final_path = model_dir / "model.zip"
        model.save(final_path)
        env.close()
        revision = git_info()
        probe = make_env(layout_path=layout_path, orders=level["orders"], reward_overrides=reward_overrides)
        metadata = {"status": "completed", "algorithm": "PPO (clonación de comportamiento)", "policy": "MlpPolicy",
                    "environment_version": ENV_VERSION, "seed": config["seed"], "orders": level["orders"],
                    "blocked": level["blocked"], "requested_timesteps": 0, "effective_timesteps": 0,
                    "layout_path": str(layout_path) if layout_path else None, "layout_sha256": probe.layout.digest,
                    "simulation": asdict(probe.config), "rewards": asdict(probe.reward_config),
                    "reward_overrides": dict(reward_overrides or {}), "hyperparameters": hyper, "n_envs": n_envs,
                    "parent_model": None, "model_path": str(final_path),
                    "bc": {**bc, "demo_seed_start": DEMO_SEED_START, "val_seed_start": VAL_SEED_START,
                           "demo_steps": int(len(demos["actions"])), "validation_steps": int(len(validation["actions"])),
                           "demos_sha256": demos_sha256(demos), "expert_clean_success": demos["expert_clean_success"],
                           "cut_episodes": demos["cut_episodes"], "fit": fit,
                           "expert": "pipelines.baselines.HeuristicPolicy"},
                    "git_revision": revision["git_commit"], "git_dirty": revision["git_dirty"] == "true",
                    "duration_seconds": time.perf_counter() - started,
                    "completed_at_utc": datetime.now(timezone.utc).isoformat()}
        write_json(run_dir / "metadata.json", metadata)
        mlflow.log_artifact(str(final_path), artifact_path="modelo")
        mlflow.log_artifact(str(run_dir / "metadata.json"), artifact_path="entrenamiento")
        mlflow.set_tags({"model_sha256": sha256_file(final_path), "pasos_reales": 0, "demos_sha256": metadata["bc"]["demos_sha256"]})
        mlflow.log_metrics({"bc/accuracy_train": fit["train"]["accuracy"], "bc/accuracy_val": fit["validation"]["accuracy"],
                            "bc/value_ev_val": fit["validation"]["value_explained_variance"] or 0.0,
                            "minutos_reales": metadata["duration_seconds"] / 60})
        metadata["mlflow_run_id"] = run.info.run_id
    return metadata


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Clonación de comportamiento desde un YAML de configs/experiments/")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    meta = run_bc(args.config, workers=args.workers)
    print(json.dumps({"model_path": meta["model_path"], "demo_steps": meta["bc"]["demo_steps"],
                      "fit": meta["bc"]["fit"], "duration_seconds": meta["duration_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
