"""CLI mínima: python -m pipelines.cli --help."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from envs import make_env
from envs.env import Action
from pipelines.baselines import make_policy
from pipelines.train import default_model, train_ppo


def demo_transitions(steps=5, orders=1, blocked=False, layout_path=None):
    env = make_env(blocked, layout_path, orders)
    observation, _ = env.reset(seed=42)
    # v2 desde BASE (3,16) mirando al norte: avance, choque con el muro interior, frenado y dos acciones inválidas.
    actions = [Action.AVANZAR, Action.AVANZAR, Action.FRENAR, Action.SUBIR, Action.CARGAR]
    transitions = []
    for index in range(steps):
        action = actions[index % len(actions)]
        previous = observation.tolist()
        observation, reward, terminated, truncated, info = env.step(action)
        transitions.append({"step": index + 1, "observation": previous,
                            "action": int(action), "action_name": action.name,
                            "resulting_state": info["state"], "reward": reward,
                            "reward_components": info["reward_components"],
                            "new_observation": observation.tolist(),
                            "terminated": terminated, "truncated": truncated})
        if terminated or truncated:
            break
    env.close()
    return transitions


def parser():
    root = argparse.ArgumentParser(description="Warehouse Rush v0.1 — simulación 2D y PPO")
    commands = root.add_subparsers(dest="command", required=True)
    view = commands.add_parser("view", help="Abrir visualización 3D Three.js en el navegador")
    view.add_argument("--port", type=int, default=8080)
    view.add_argument("--no-open", action="store_true", help="No abrir navegador automáticamente")
    view.add_argument("--layout", type=Path)
    for name in ("map", "validate", "demo-transitions", "play", "train", "evaluate", "compare"):
        command = commands.add_parser(name)
        command.add_argument("--layout", type=Path, help="JSON de mapa/configuración")
        command.add_argument("--orders", type=int, choices=(1, 2), default=1)
        command.add_argument("--blocked", action="store_true")
        if name == "demo-transitions":
            command.add_argument("--steps", type=int, default=5)
        if name == "play":
            command.add_argument("--policy", choices=("random", "heuristic", "ppo", "dqn"), default="heuristic")
            command.add_argument("--seed", type=int, default=10_000)
            command.add_argument("--model", type=Path)
            command.add_argument("--delay", type=float, default=0.1, help="Segundos por transición")
            command.add_argument("--no-render", action="store_true")
        if name == "train":
            command.add_argument("--algo", choices=("ppo", "dqn"), default="ppo")
            command.add_argument("--timesteps", type=int, default=20_000)
            command.add_argument("--seed", type=int, default=42)
            command.add_argument("--n-steps", type=int, default=500)
            command.add_argument("--batch-size", type=int, default=100)
            command.add_argument("--run-name")
        if name in ("evaluate", "compare"):
            command.add_argument("--episodes", type=int, default=20)
            command.add_argument("--seed-start", type=int, default=10_000)
            command.add_argument("--model", type=Path)
            command.add_argument("--output", type=Path, default=Path("docs/resultados"))
            if name == "evaluate":
                command.add_argument("--policy", choices=("random", "heuristic", "ppo", "dqn"), default="ppo")
            else:
                command.add_argument("--policies", nargs="+", choices=("random", "heuristic", "ppo", "dqn"),
                                     default=["random", "heuristic", "ppo"])
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "view":
        from api._viewer import serve_viewer

        serve_viewer(args.port, not args.no_open, args.layout)
    elif args.command == "map":
        env = make_env(args.blocked, args.layout, args.orders)
        env.reset(seed=42)
        print(env.render())
        print("# pared; R rack; B base; 1/2 recogidas; D entrega; : paso abierto; X bloqueo; ^>v< robot")
        print(f"BASE={env.layout.base}; robot inicia sobre BASE; estaciones={env.layout.stations}")
        env.close()
    elif args.command == "validate":
        from stable_baselines3.common.env_checker import check_env

        env = make_env(args.blocked, args.layout, args.orders)
        check_env(env, warn=True)
        print(json.dumps(env.layout.validate_routes(), indent=2))
        env.close()
        tests = Path(__file__).resolve().parents[1] / "tests"
        if not tests.is_dir():
            raise FileNotFoundError("validate requiere el checkout con tests/ (pip install -r requirements.txt)")
        code = subprocess.call([sys.executable, "-m", "pytest", str(tests), "-q"])
        if code:
            raise SystemExit(code)
    elif args.command == "demo-transitions":
        if args.steps < 1:
            raise ValueError("steps debe ser positivo")
        print(json.dumps(demo_transitions(args.steps, args.orders, args.blocked, args.layout), indent=2))
    elif args.command == "play":
        if args.delay < 0:
            raise ValueError("delay no puede ser negativo")
        env = make_env(args.blocked, args.layout, args.orders)
        policy = make_policy(args.policy, args.seed, args.model or default_model(args.orders))
        observation, info = env.reset(seed=args.seed)
        if not args.no_render:
            print(env.render())
        done = False
        while not done:
            action = policy.action(observation, env)
            observation, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            if not args.no_render:
                print(f"\n{Action(action).name}: reward={reward:.3f}\n{env.render()}")
                if args.delay:
                    time.sleep(args.delay)
        print(json.dumps(info, indent=2))
        env.close()
    elif args.command == "train":
        result = train_ppo(timesteps=args.timesteps, seed=args.seed, orders=args.orders,
                           blocked=args.blocked, layout_path=args.layout, n_steps=args.n_steps if args.algo == "ppo" else None,
                           batch_size=args.batch_size if args.algo == "ppo" else None, run_name=args.run_name, algo=args.algo)
        print(json.dumps({key: result[key] for key in ("status", "effective_timesteps", "duration_seconds", "model_path", "model_alias")}, indent=2))
    else:
        from pipelines.evaluate import evaluate, summary_table

        result = evaluate(policies=(args.policy,) if args.command == "evaluate" else args.policies,
                          orders=args.orders, episodes=args.episodes, seed_start=args.seed_start,
                          scenarios=(args.blocked,) if args.command == "evaluate" else (False, True),
                          model_path=args.model, layout_path=args.layout, output_dir=args.output)
        print(summary_table(result))
        print(f"Resultados: {args.output}/evaluation.csv, evaluation.json, report.md")
        if not result["completed"]:
            print(json.dumps(result["errors"], indent=2), file=sys.stderr)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
