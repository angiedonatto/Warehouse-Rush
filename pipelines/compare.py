"""Comparación de finalistas × semillas y curvas de entrenamiento y evaluación por separado.

Uso:
  python -m pipelines.compare --config configs/comparaciones/finalistas-m1-v1.yaml
  python -m pipelines.compare --curves m1-c3-seed0 [m1-e4y-seed3 ...]

La comparación NO evalúa modelos: lee las evaluaciones congeladas de cada run en su suite
(docs/resultados/eval/<run>/evaluation.csv, un registro por episodio) y los metadatos de entrenamiento
(docs/resultados/training/<run>/metadata.json). Cada semilla de entrenamiento pesa lo mismo: la unidad de
la comparación es el entrenamiento independiente, no el episodio de evaluación.

Las curvas separan las dos fuentes que pide el enunciado:
  - entrenamiento: política estocástica (con exploración), episodios del Monitor de los ambientes de
    entrenamiento (`episodes.monitor.csv`);
  - evaluación: política determinista, ambiente aparte, 5 episodios cada 20 000 pasos
    (`periodic_eval/evaluations.npz`), que es lo que elige `best/`.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import yaml

EVAL_ROOT = Path("docs/resultados/eval")
TRAIN_ROOT = Path("docs/resultados/training")
SCENARIOS = {"abierto": "normal", "cerrado": "blocked"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def run_summary(run: str, scenario: str = "normal", policy: str = "ppo", eval_root: Path = EVAL_ROOT,
                train_root: Path = TRAIN_ROOT) -> dict:
    """Métricas de misión de un run en su suite, desde los registros por episodio."""
    with (eval_root / run / "evaluation.csv").open() as handle:
        rows = [r for r in csv.DictReader(handle) if r["policy"] == policy and r["scenario"] == scenario]
    if not rows:
        raise ValueError(f"{run}: sin episodios de {policy} en el escenario {scenario}")
    success = [r["success"] == "True" for r in rows]
    ok_steps = [float(r["steps"]) for r, s in zip(rows, success) if s]
    ends: dict[str, int] = {}
    for r in rows:
        ends[r["end_reason"]] = ends.get(r["end_reason"], 0) + 1
    meta_path = train_root / run / "metadata.json"  # las líneas base no tienen entrenamiento
    meta = _read_json(meta_path) if meta_path.is_file() else {}
    return {
        "run": run, "seed": meta.get("seed"), "episodes": len(rows),
        "success_rate": float(np.mean(success)),
        "mean_collisions": float(np.mean([float(r["collisions"]) for r in rows])),
        "mean_invalid": float(np.mean([float(r["invalid_interactions"]) for r in rows])),
        "mean_deliveries": float(np.mean([float(r["deliveries"]) for r in rows])),
        "mean_pickups": float(np.mean([float(r["pickups"]) for r in rows])),
        "mean_steps_successes": float(np.mean(ok_steps)) if ok_steps else None,
        "end_reasons": dict(sorted(ends.items())),
        "budget_steps": meta.get("effective_timesteps"),
        "train_minutes": round(meta["duration_seconds"] / 60, 1) if meta.get("duration_seconds") else None,
        "stagnation_window": meta.get("stagnation_window"),
        "reward_overrides": meta.get("reward_overrides") or {},
    }


def bootstrap_mean_ci(values, n: int = 10_000, seed: int = 0, level: float = 0.95) -> list[float]:
    """Intervalo bootstrap (percentil) de la media entre semillas; semilla fija para que sea reproducible."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(n, len(values)), replace=True).mean(axis=1)
    alpha = (1 - level) / 2
    return [float(np.quantile(means, alpha)), float(np.quantile(means, 1 - alpha))]


def recipe_summary(name: str, runs: list[str], threshold: float, scenario: str = "normal", **roots) -> dict:
    per_seed = [run_summary(r, scenario, **roots) for r in runs]
    rates = [s["success_rate"] for s in per_seed]
    return {
        "recipe": name, "n_seeds": len(runs), "runs": per_seed,
        "mean_success": float(np.mean(rates)), "std_success": float(np.std(rates, ddof=1)) if len(rates) > 1 else 0.0,
        "ci95_mean_success": bootstrap_mean_ci(rates),
        "seeds_at_threshold": sum(r >= threshold for r in rates),
        "mean_collisions": float(np.mean([s["mean_collisions"] for s in per_seed])),
        "mean_invalid": float(np.mean([s["mean_invalid"] for s in per_seed])),
        "train_minutes_total": round(sum(s["train_minutes"] or 0 for s in per_seed), 1),
        "budget_steps_each": sorted({s["budget_steps"] for s in per_seed}),
    }


def decide(recipes: list[dict], rule: dict) -> dict:
    """Aplica la regla pre-registrada: gana la mayor media de éxito entre semillas, salvo que la diferencia en
    semillas que alcanzan el umbral sea <= `margen_semillas`; entonces gana la receta con menos términos de
    recompensa fuera del valor por defecto (desempate declarado)."""
    ranked = sorted(recipes, key=lambda r: r["mean_success"], reverse=True)
    best, other = ranked[0], ranked[1]
    gap = best["seeds_at_threshold"] - other["seeds_at_threshold"]
    if gap > rule["margen_semillas"]:
        return {"selected": best["recipe"], "reason": f"más semillas que funcionan ({best['seeds_at_threshold']} frente a {other['seeds_at_threshold']})", "distinguishable": True}
    for r in recipes:
        if any(s["reward_overrides"] != r["runs"][0]["reward_overrides"] for s in r["runs"]):
            raise ValueError(f"{r['recipe']}: las semillas no comparten la recompensa; no es una receta")
    terms = {r["recipe"]: len(r["runs"][0]["reward_overrides"]) for r in recipes}
    simplest = min(recipes, key=lambda r: (terms[r["recipe"]], -r["mean_success"]))
    return {"selected": simplest["recipe"],
            "reason": (f"diferencia de {gap} semilla(s) que alcanzan el umbral (<= {rule['margen_semillas']}): "
                       f"no distinguible; desempate por menos términos de recompensa ({terms})"),
            "distinguishable": False}


def compare(config_path: Path, output_root: Path = Path("docs/resultados/comparacion"), **roots) -> dict:
    config = yaml.safe_load(Path(config_path).read_text())
    threshold = config["regla"]["umbral_exito_semilla"]
    scenario = SCENARIOS[config.get("escenario", "abierto")]
    recipes = [recipe_summary(name, spec["runs"], threshold, scenario, **roots)
               for name, spec in config["finalistas"].items()]
    references = {}
    for name, spec in (config.get("referencias") or {}).items():
        references[name] = recipe_summary(name, spec["runs"], threshold, scenario, **roots)
    baselines = {}
    first_run = next(iter(config["finalistas"].values()))["runs"][0]
    for policy in ("random", "heuristic"):
        try:
            baselines[policy] = run_summary(config.get("linea_base_run", first_run), scenario, policy, **roots)
        except ValueError:
            pass
    result = {"id": config["id"], "suite": config["suite"], "scenario": scenario, "rule": config["regla"],
              "recipes": recipes, "references": references, "baselines": baselines,
              "decision": decide(recipes, config["regla"]),
              "per_seed_unit": "cada semilla de entrenamiento pesa lo mismo; IC bootstrap de la media entre semillas"}
    out = output_root / config["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "comparison.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (out / "report.md").write_text(render_report(result, config))
    curves = config.get("curvas", True)
    if curves:
        for recipe in recipes:
            for s in recipe["runs"]:
                plot_learning_curves(s["run"], out / "curvas" / f"{s['run']}.png", **roots)
    return result


def _pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def _num(x, nd=1):
    return "—" if x is None else f"{x:.{nd}f}"


def render_report(result: dict, config: dict) -> str:
    rule = result["rule"]
    lines = [f"# Comparación de finalistas `{result['id']}`", "",
             f"Suite `{result['suite']}` (escenario {result['scenario']}), modelo final de cada run, PPO determinista. "
             "Cada semilla de entrenamiento es una unidad; el IC 95% es bootstrap de la media entre semillas.", "",
             "## Por receta", "",
             f"| Receta | Semillas | Éxito medio ± sd | IC 95% | Semillas ≥ {_pct(rule['umbral_exito_semilla'])} | Choques/ep | Inválidas/ep | Pasos c/u | Minutos totales |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in result["recipes"] + list(result["references"].values()):
        ref = " (referencia)" if r["recipe"] in result["references"] else ""
        lines.append(f"| {r['recipe']}{ref} | {r['n_seeds']} | {_pct(r['mean_success'])} ± {100 * r['std_success']:.0f} | "
                     f"{_pct(r['ci95_mean_success'][0])}–{_pct(r['ci95_mean_success'][1])} | {r['seeds_at_threshold']}/{r['n_seeds']} | "
                     f"{_num(r['mean_collisions'], 2)} | {_num(r['mean_invalid'])} | {', '.join(f'{b:,}'.replace(',', ' ') for b in r['budget_steps_each'])} | {r['train_minutes_total']} |")
    lines += ["", "## Por semilla", "",
              "| Receta | Run | Éxito | Choques/ep | Inválidas/ep | Recogidas/ep | Entregas/ep | Pasos de los éxitos | Motivo de fin | Minutos |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|---:|"]
    for r in result["recipes"] + list(result["references"].values()):
        for s in r["runs"]:
            ends = ", ".join(f"{k} {v}" for k, v in s["end_reasons"].items())
            lines.append(f"| {r['recipe']} | {s['run']} | {_pct(s['success_rate'])} | {_num(s['mean_collisions'], 2)} | {_num(s['mean_invalid'])} | "
                         f"{_num(s['mean_pickups'], 2)} | {_num(s['mean_deliveries'], 2)} | {_num(s['mean_steps_successes'])} | {ends} | {_num(s['train_minutes'])} |")
    if result["baselines"]:
        lines += ["", "## Líneas base en la misma suite", "", "| Política | Éxito | Choques/ep | Inválidas/ep | Pasos de los éxitos |", "|---|---:|---:|---:|---:|"]
        for name, s in result["baselines"].items():
            lines.append(f"| {name} | {_pct(s['success_rate'])} | {_num(s['mean_collisions'], 2)} | {_num(s['mean_invalid'])} | {_num(s['mean_steps_successes'])} |")
    d = result["decision"]
    lines += ["", "## Decisión (regla pre-registrada)", "", f"- **Seleccionada: `{d['selected']}`** — {d['reason']}.",
              f"- Distinguible con estas semillas: {'sí' if d['distinguishable'] else 'no'}.",
              "", "Curvas de entrenamiento (estocástica) y de evaluación (determinista) por run: `curvas/`.", ""]
    return "\n".join(lines)


def training_episodes(run: str, train_root: Path = TRAIN_ROOT):
    """Episodios del Monitor de entrenamiento y el contador de pasos al terminar cada uno. Si el run continúa
    a un padre (parent_model), el contador empieza en los pasos efectivos del padre, como num_timesteps."""
    run_dir = train_root / run
    meta = _read_json(run_dir / "metadata.json")
    with (run_dir / "episodes.monitor.csv").open() as handle:
        next(handle)  # cabecera de metadatos del Monitor
        rows = list(csv.DictReader(handle))
    offset = 0
    if meta.get("parent_model"):
        parent_meta = train_root / Path(meta["parent_model"]).parts[1] / "metadata.json"
        offset = _read_json(parent_meta).get("effective_timesteps", 0) if parent_meta.is_file() else 0
    # VecMonitor intercala los episodios de los n_envs ambientes; el acumulado de sus longitudes es el
    # contador global de pasos de entorno (el mismo que num_timesteps de SB3), salvo episodios sin terminar.
    steps = offset + np.cumsum([int(r["l"]) for r in rows])
    return rows, steps, offset


def plot_learning_curves(run: str, output: Path, window: int = 200, train_root: Path = TRAIN_ROOT, **_) -> bool:
    """Dos paneles separados: entrenamiento (política estocástica, con exploración) y evaluación periódica
    (política determinista, ambiente aparte). El eje x es el contador de pasos del run (incluye al padre)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    run_dir = train_root / run
    rows, steps, offset = training_episodes(run, train_root)
    if len(rows) < 2:
        return False
    returns = np.array([float(r["r"]) for r in rows])
    success = np.array([r.get("success") == "True" for r in rows], dtype=float)
    w = min(window, len(rows))
    kernel = np.ones(w) / w
    fig, (ax_train, ax_eval) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    ax_train.plot(steps[w - 1:], np.convolve(returns, kernel, mode="valid"), color="#3b6ea5", label=f"Retorno (media móvil {w} episodios)")
    ax_train.set_ylabel("Retorno")
    ax_rate = ax_train.twinx()
    ax_rate.plot(steps[w - 1:], 100 * np.convolve(success, kernel, mode="valid"), color="#c0504d", label="Éxito %")
    ax_rate.set_ylabel("Éxito %")
    ax_rate.set_ylim(-5, 105)
    ax_train.set_title(f"{run} — entrenamiento: política estocástica (con exploración), {len(rows)} episodios")
    handles = ax_train.get_legend_handles_labels()[0] + ax_rate.get_legend_handles_labels()[0]
    ax_train.legend(handles, [h.get_label() for h in handles], fontsize=8, loc="lower right")
    npz = run_dir / "periodic_eval" / "evaluations.npz"
    if npz.is_file():
        with np.load(npz) as data:
            t, res = data["timesteps"], data["results"]
        mean, std = res.mean(axis=1), res.std(axis=1)
        ax_eval.plot(t, mean, color="#2e7d32", marker=".", label=f"Retorno medio ({res.shape[1]} episodios)")
        ax_eval.fill_between(t, mean - std, mean + std, color="#2e7d32", alpha=0.15, label="± 1 sd")
        best = int(np.argmax(mean))
        ax_eval.axvline(t[best], color="#555", ls="--", lw=1, label=f"mejor checkpoint ({t[best]:,} pasos)".replace(",", " "))
        ax_eval.legend(fontsize=8, loc="lower right")
    else:
        ax_eval.text(0.5, 0.5, "sin evaluación periódica", ha="center", transform=ax_eval.transAxes)
    ax_eval.set_title("evaluación periódica: política determinista, ambiente aparte (semilla inicial 20000)")
    ax_eval.set_ylabel("Retorno")
    ax_eval.set_xlabel("Pasos de entorno (contador del run" + (", incluye al padre)" if offset else ")"))
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=120)
    plt.close(fig)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="YAML de configs/comparaciones/")
    group.add_argument("--curves", nargs="+", help="runs a los que dibujar las curvas separadas")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.config:
        result = compare(Path(args.config), **({"output_root": Path(args.output)} if args.output else {}))
        for r in result["recipes"]:
            print(f"{r['recipe']}: {r['seeds_at_threshold']}/{r['n_seeds']} semillas, media {100 * r['mean_success']:.1f}%")
        print("seleccionada:", result["decision"]["selected"], "-", result["decision"]["reason"])
    else:
        out = Path(args.output or "docs/resultados/curvas")
        for run in args.curves:
            print(run, plot_learning_curves(run, out / f"{run}.png"))


if __name__ == "__main__":
    main()
