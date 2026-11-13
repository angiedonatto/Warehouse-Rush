"""Episodios reales, semillas emparejadas, métricas y reporte académico."""

import csv
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

import numpy as np

from envs import __version__
from envs import make_env
from pipelines.baselines import RandomPolicy, make_policy
from pipelines.train import default_model, plot_training_curve, write_json

METRICS = ("total_reward", "steps", "distance", "battery_used", "collisions", "invalid_interactions", "deliveries")
EPISODE_FIELDS = ["policy", "scenario", "orders", "seed", "success", "end_reason", *METRICS,
                  "pickups", "final_x", "final_y", "final_stage",
                  *[f"action_{i}_count" for i in range(8)]]


def evaluate(*, policies=("random", "heuristic", "ppo"), orders=1, episodes=20,
             seed_start=10_000, scenarios=(False, True), model_path=None,
             layout_path=None, output_dir="docs/resultados") -> dict:
    if episodes < 1 or seed_start < 0 or seed_start <= 42 < seed_start + episodes:
        raise ValueError("episodes > 0 y semillas no negativas distintas de entrenamiento (42)")
    if not policies or len(set(policies)) != len(policies):
        raise ValueError("Selecciona políticas distintas")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model_path = Path(model_path) if model_path else default_model(orders)
    rows, summaries, errors = [], [], []
    probe = make_env(layout_path=layout_path, orders=orders)
    configuration = {"environment_version": __version__, "orders": orders,
                     "episodes_per_combination": episodes,
                     "seeds": list(range(seed_start, seed_start + episodes)),
                     "layout_sha256": probe.layout.digest, "scenario": probe.layout.data,
                     "simulation": asdict(probe.config), "rewards": asdict(probe.reward_config),
                     "ppo_deterministic": True, "reward_std_ddof": 0}
    probe.close()
    training = None
    if any(p in policies for p in ("ppo", "dqn")) and model_path.is_file():
        configuration["model_path"] = str(model_path)
        configuration["model_sha256"] = sha256(model_path.read_bytes()).hexdigest()
        metadata_path = model_path.with_suffix(".json")
        if not metadata_path.exists():
            # Modelo en su directorio original.
            candidate = Path("docs/resultados/training") / model_path.parent.name / "metadata.json"
            metadata_path = candidate
        if metadata_path.exists():
            training = json.loads(metadata_path.read_text())
            configuration["training_metadata"] = training
            metrics_path = Path("docs/resultados/training") / Path(training["model_path"]).parent.name / "metrics.json"
            if metrics_path.is_file():
                configuration["training_metrics"] = json.loads(metrics_path.read_text())
            if training["seed"] in configuration["seeds"]:
                raise ValueError("Las semillas de evaluación deben ser distintas de entrenamiento")
            if training["layout_sha256"] != configuration["layout_sha256"]:
                raise ValueError("El mapa de evaluación difiere del mapa de entrenamiento")
    for blocked in scenarios:
        for policy_name in policies:
            env = make_env(blocked, layout_path, orders)
            combination = []
            try:
                policy = make_policy(policy_name, seed_start, model_path)
                for seed in configuration["seeds"]:
                    if policy_name == "random":
                        policy = RandomPolicy(seed)
                    observation, _ = env.reset(seed=seed)
                    done = False
                    action_counts = [0] * env.action_space.n
                    while not done:
                        action = policy.action(observation, env)
                        action_counts[action] += 1
                        observation, _, terminated, truncated, info = env.step(action)
                        done = terminated or truncated
                    row = {"policy": policy_name, "scenario": "blocked" if blocked else "normal",
                           "orders": orders, "seed": seed, "success": info["success"],
                           "end_reason": info["end_reason"],
                           **{key: info[key] for key in METRICS},
                           "pickups": len(env.picked_packages), "final_x": env.state.x,
                           "final_y": env.state.y, "final_stage": env.state.etapa,
                           **{f"action_{i}_count": count for i, count in enumerate(action_counts)}}
                    rows.append(row)
                    combination.append(row)
                summary = {"policy": policy_name, "scenario": "blocked" if blocked else "normal",
                           "episodes": len(combination),
                           "success_rate": float(np.mean([r["success"] for r in combination])),
                           "reward_std": float(np.std([r["total_reward"] for r in combination], ddof=0)),
                           **{f"mean_{key}": float(np.mean([r[key] for r in combination])) for key in METRICS},
                           "mean_pickups": float(np.mean([r["pickups"] for r in combination])),
                           "action_counts": {str(i): sum(r[f"action_{i}_count"] for r in combination) for i in range(8)},
                           "end_reasons": {reason: sum(r["end_reason"] == reason for r in combination)
                                           for reason in sorted({r["end_reason"] for r in combination})}}
                summaries.append(summary)
            except Exception as exc:
                errors.append({"policy": policy_name, "blocked": blocked,
                               "completed_episodes": len(combination),
                               "error": f"{type(exc).__name__}: {exc}"})
            finally:
                env.close()
    deltas = []
    for name in policies:
        groups = {s["scenario"]: s for s in summaries if s["policy"] == name}
        if "normal" in groups and "blocked" in groups:
            keys = ["success_rate", "reward_std", *[f"mean_{m}" for m in METRICS]]
            deltas.append({"policy": name, **{key: groups["blocked"][key] - groups["normal"][key] for key in keys}})
    result = {"completed": not errors, "configuration": configuration,
              "summary": summaries, "blocked_minus_normal": deltas, "errors": errors,
              "episodes": rows}
    write_json(output / "evaluation.json", result)
    # También reemplazar datos anteriores por cabecera vacía si falla toda la ejecución.
    with (output / "evaluation.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EPISODE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output / "report.md").write_text(report(result), encoding="utf-8")
    if training:
        source = Path("docs/resultados/training") / Path(training["model_path"]).parent.name / "episodes.monitor.csv"
        if source.is_file():
            plot_training_curve(source, output / "training_curve.png")
    return result


def summary_table(result: dict) -> str:
    lines = ["| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in result["summary"]:
        lines.append(f"| {row['policy']} | {row['scenario']} | {100 * row['success_rate']:.0f}% | "
                     f"{row['mean_total_reward']:.3f} ± {row['reward_std']:.3f} | {row['mean_steps']:.1f} | "
                     f"{row['mean_distance']:.1f} | {row['mean_battery_used']:.2f} | {row['mean_collisions']:.1f} | "
                     f"{row['mean_invalid_interactions']:.1f} | {row['mean_deliveries']:.1f} |")
    return "\n".join(lines)


def report(result: dict) -> str:
    config = result["configuration"]
    training = config.get("training_metadata")
    lines = ["# Warehouse Rush v0.1 — evaluación real", "", "## Configuración experimental", "",
             f"Estado: **{'completada' if result['completed'] else 'incompleta: revisar errores'}**. "
             f"Misión de {config['orders']} pedido(s); {config['episodes_per_combination']} episodios por combinación. "
             f"Semillas emparejadas {config['seeds'][0]}–{config['seeds'][-1]}. "
             "PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.", "",
             f"Mapa SHA-256: `{config['layout_sha256']}`. Mismo JSON, acciones, recompensas, "
             "batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.", ""]
    if training:
        lines += [f"{training.get('algorithm', 'PPO')}: semilla {training['seed']}, {training['effective_timesteps']} pasos efectivos "
                  f"({training['requested_timesteps']} solicitados), "
                  f"{training['duration_seconds']:.2f} s reales; entrenado con bloqueo={training['blocked']}. "
                  f"Modelo final: `{config['model_path']}`. SHA-256: `{config['model_sha256']}`. "
                  "Los hiperparámetros y versiones completos están en `evaluation.json`.", ""]
    lines += ["## Hechos medidos", "", summary_table(result), "",
              "La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; "
              "JSON conserva configuración, agregados, acciones y errores.", "", "## Robustez: bloqueo menos normal", "",
              "| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |",
              "|---|---:|---:|---:|---:|---:|"]
    for row in result["blocked_minus_normal"]:
        lines.append(f"| {row['policy']} | {100 * row['success_rate']:.1f} | {row['mean_total_reward']:.3f} | "
                     f"{row['mean_steps']:.1f} | {row['mean_distance']:.1f} | {row['mean_battery_used']:.2f} |")
    lines += ["", "La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: "
              "el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total "
              "recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa "
              "mayor entre escenarios no demuestra mayor eficiencia.",
              "", "## Interpretación basada en datos", ""]
    metrics = config.get("training_metrics")
    if metrics and metrics["completed_training_episodes"]:
        lines += [f"En entrenamiento se completaron {metrics['completed_training_episodes']} episodios, "
                  f"con {metrics['training_successes']} éxitos. El retorno medio de los primeros 10 fue "
                  f"{metrics['first_10_episode_mean_reward']:.3f} y el de los últimos 10 fue "
                  f"{metrics['last_10_episode_mean_reward']:.3f}. Mejor retorno por sí solo no acredita "
                  "haber aprendido a recoger y entregar.", ""]
    for row in result["summary"]:
        if row["policy"] in ("ppo", "dqn"):
            lines.append(f"- {row['policy'].upper()} en {row['scenario']}: éxito **{100 * row['success_rate']:.0f}%**, "
                         f"{row['mean_pickups']:.2f} recogidas medias, finales {row['end_reasons']}, "
                         f"conteos de acciones 0–7: {row['action_counts']}.")
            if row["action_counts"].get("3", 0) == row["episodes"] * config["simulation"]["max_steps"]:
                lines.append("- La política final elige FRENAR en todos los pasos, permanece en BASE y "
                             "evita penalizaciones mayores sin cumplir la misión. Es el comportamiento "
                             "observado en esta evaluación determinista.")
            heuristic = next((r for r in result["summary"] if r["policy"] == "heuristic" and r["scenario"] == row["scenario"]), None)
            if heuristic and heuristic["success_rate"] > row["success_rate"]:
                lines.append(f"- En {row['scenario']}, el heurístico funciona mejor que {row['policy'].upper()} en tasa de éxito.")
            if row["success_rate"] == 0:
                lines.append("- El entrenamiento ejecutado no resolvió la misión. Las señales densas de "
                             "distancia no garantizan descubrir la secuencia detenerse–orientarse–interactuar; "
                             "ésta es una hipótesis de diagnóstico, no una causa demostrada. "
                             "No se cambiaron las recompensas para mejorar la cifra.")
    lines += ["", "## Limitaciones", "",
              "- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: "
              "la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.",
              "- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.",
              "- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. "
              "PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.",
              "- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.",
              "- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración "
              "y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija."]
    if result["errors"]:
        lines += ["", "## Errores reales", "", "```json", json.dumps(result["errors"], indent=2), "```"]
    return "\n".join(lines) + "\n"
