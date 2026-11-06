import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from warehouse_rush import tracking
from warehouse_rush.agent import QAgent
from warehouse_rush.env import ACTION_NAMES, MOVES, GridEnv

MODEL_DIR = "models"


def evaluate(agent, env, seeds):
    """Greedy rollouts on fixed layouts -> (success rate, optimal-path rate, mean steps)."""
    wins = optimal = steps = 0
    for seed in seeds:
        obs, info = env.reset(seed=int(seed))
        done = False
        while not done:
            obs, _, term, trunc, step_info = env.step(agent.act(obs))
            done = term or trunc
        wins += term
        optimal += term and env.steps == info["optimal_length"]
        steps += env.steps
    n = len(seeds)
    return wins / n, optimal / n, steps / n


def fmt_obstacles(obstacles):
    return ", ".join(f"({x},{y})" for x, y in obstacles)


def train(env, agent, cfg, run=None, show_steps=True):
    t, es = cfg["train"], cfg["early_stopping"]
    n = t["max_episodes"]
    decay_eps = max(1, int(t["eps_decay_fraction"] * n))
    eval_env = GridEnv(env.size, env.n_obstacles)
    eval_seeds = np.random.default_rng(12345).integers(0, 2**31, es["eval_layouts"])

    best, best_q, stale, stopped_early = (-1.0, -1.0), agent.q.copy(), 0, False
    best_metrics, window = {}, []
    for ep in range(1, n + 1):
        eps = max(t["eps_end"], t["eps_start"] - (t["eps_start"] - t["eps_end"]) * ep / decay_eps)
        obs, info = env.reset()
        print(f"\n=== Train episode {ep}/{n}  epsilon={eps:.3f} ===")
        print(f"optimal_length={info['optimal_length']}  obstacles "
              f"({len(info['obstacles'])}): {fmt_obstacles(info['obstacles'])}")
        done, total, step = False, 0.0, 0
        while not done:
            step += 1
            before = env.pos
            a = agent.act(obs, eps)
            nxt, r, term, trunc, step_info = env.step(a)
            agent.update(obs, a, r, nxt, term)
            obs, done, total = nxt, term or trunc, total + r
            if show_steps:
                print(f"  step {step:>3}: {before} {ACTION_NAMES[a]:<5} -> {env.pos} "
                      f"{step_info['event']:<4} reward={r:+.0f}")
        print(f"  {'GOAL' if term else 'TIMEOUT'} in {step} steps, return={total:.0f}")
        window.append(term)
        if run:
            run.metric("episode_return", total, ep)
            run.metric("episode_steps", step, ep)
            run.metric("episode_success", float(term), ep)
            run.metric("epsilon", eps, ep)

        if ep % es["eval_every"] == 0:
            success, opt, mean_steps = evaluate(agent, eval_env, eval_seeds)
            score = (success, opt)
            improved = score[0] + score[1] > best[0] + best[1] + es["min_delta"]
            if improved:
                best, best_q, stale = score, agent.q.copy(), 0
                best_metrics = {"eval_success": success, "eval_optimal": opt, "eval_mean_steps": mean_steps}
            else:
                stale += 1
            print(f"\n--- eval @ {ep}: success={success:.1%} optimal={opt:.1%} "
                  f"mean_steps={mean_steps:.1f} best={best[0]:.1%}/{best[1]:.1%} "
                  f"stale={stale}/{es['patience']} ---")
            if run:
                run.metric("eval_success", success, ep)
                run.metric("eval_optimal", opt, ep)
                run.metric("eval_mean_steps", mean_steps, ep)
                run.flush()
            if ep >= es["min_episodes"] and stale >= es["patience"]:
                print(f"EARLY STOP at episode {ep}: no improvement for {stale} evaluations")
                stopped_early = True
                break
    agent.q = best_q  # restore the best checkpoint
    best_metrics["episodes_trained"] = ep
    return best_metrics, stopped_early


def play(env, agent, episodes, seed, verbose=True):
    results = []
    for ep in range(1, episodes + 1):
        obs, info = env.reset(seed=None if seed is None else seed + ep)
        print(f"\n=== Episode {ep} ===")
        print(f"start={env.start} goal={env.goal} optimal_length={info['optimal_length']}")
        print(f"obstacles ({len(info['obstacles'])}): {fmt_obstacles(info['obstacles'])}")
        print(env.render())
        total, done, step = 0.0, False, 0
        while not done:
            step += 1
            before = env.pos
            blocked = [n for n, (dx, dy) in zip(ACTION_NAMES, MOVES)
                       if env._blocked((before[0] + dx, before[1] + dy))]
            a = agent.act(obs)
            q = agent.q[tuple(obs)]
            obs, r, term, trunc, info = env.step(a)
            total += r
            done = term or trunc
            if verbose:
                print(f"  step {step:>3}: at {before} blocked={blocked or 'none'} "
                      f"Q={np.round(q, 1).tolist()} -> {ACTION_NAMES[a]:<5} "
                      f"=> {env.pos} {info['event']} reward={r:+.0f}")
        opt = info["optimal_length"]
        print(f"{'REACHED GOAL' if term else 'TIMED OUT'} in {step} steps (optimal {opt}), return={total:.0f}")
        print(env.render())
        results.append((term, step, opt))
    ok = [r for r in results if r[0]]
    optimal = sum(1 for _, s, o in ok if s == o)
    print(f"\nSummary: {len(ok)}/{len(results)} reached goal, {optimal} with optimal path")


def load_config(path, args):
    cfg = yaml.safe_load(Path(path).read_text())
    if args.size is not None:
        cfg["env"]["size"] = args.size
    if args.obstacles is not None:
        cfg["env"]["n_obstacles"] = args.obstacles
    if args.episodes is not None:
        cfg["train"]["max_episodes"] = args.episodes
    if args.seed is not None:
        cfg["train"]["seed"] = args.seed
    return cfg


def flat(cfg):
    return {f"{k}.{kk}": vv for k, v in cfg.items() for kk, vv in v.items()}


def main():
    p = argparse.ArgumentParser(prog="warehouse_rush")
    p.add_argument("command", choices=["train", "play"])
    p.add_argument("--params", default="params.yaml")
    p.add_argument("--size", type=int)
    p.add_argument("--obstacles", type=int)
    p.add_argument("--episodes", type=int)
    p.add_argument("--seed", type=int)
    p.add_argument("--model-dir", default=MODEL_DIR)
    p.add_argument("--quiet", action="store_true", help="hide per-step lines (train and play)")
    p.add_argument("--no-mlflow", action="store_true")
    p.add_argument("--push-hf", metavar="REPO_ID", help="train: upload model to the Hugging Face Hub")
    args = p.parse_args()

    cfg = load_config(args.params, args)
    env = GridEnv(cfg["env"]["size"], cfg["env"]["n_obstacles"])
    seed = cfg["train"]["seed"]
    env.reset(seed=seed)
    agent = QAgent(cfg["env"]["size"], cfg["train"]["alpha"], cfg["train"]["gamma"], seed=seed)

    if args.command == "train":
        run = None if args.no_mlflow else tracking.Run(flat(cfg))
        metrics, stopped = train(env, agent, cfg, run, show_steps=not args.quiet)
        tracking.write_model_dir(args.model_dir, agent, cfg, metrics)
        Path("metrics.json").write_text(json.dumps(metrics, indent=2))
        if run:
            run.finish(args.model_dir, metrics, stopped)
        print(f"\nsaved {args.model_dir}/ and metrics.json: {metrics}")
        if args.push_hf:
            tracking.push_to_hub(args.model_dir, args.push_hf)
    else:
        agent.load(Path(args.model_dir) / "qtable.npy")
        play(env, agent, args.episodes or 3, seed + 10_000, verbose=not args.quiet)
