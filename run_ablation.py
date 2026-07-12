"""Run controlled ablation experiments on ARIA World."""
import sys
sys.path.insert(0, '.')

from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner
from aria_world.ablation import AblationStudy, AblationResult

DAYS = 100
AGENTS = 8
RUNS = 5
SEEDS = list(range(1, RUNS + 1))


def extract_metrics(result: dict) -> dict:
    return {
        "survival_rate": result.get("survival_rate", 0),
        "average_happiness": result.get("average_happiness", 0),
        "total_births": result.get("total_births", 0),
        "total_conflicts": result.get("total_conflicts", 0),
        "final_population": result.get("final_population", 0),
        "knowledge_total": result.get("knowledge_stats", {}).get("total", 0),
        "teachings_total": result.get("knowledge_stats", {}).get("total_teachings", 0),
        "teachings_successful": result.get("knowledge_stats", {}).get("successful_teachings", 0),
        "experts": result.get("expertise_stats", {}).get("experts", 0),
        "recipes": result.get("innovation_stats", {}).get("total_recipes", 0),
        "innovations": result.get("innovation_stats", {}).get("total_innovations", 0),
        "knowledge_avg_level": result.get("knowledge_stats", {}).get("average_level", 0),
    }


def run_condition(name: str, modify_fn, seeds: list[int]) -> list[dict]:
    results = []
    for seed in seeds:
        config = SimulationConfig(seed=seed, initial_agents=AGENTS, max_days=DAYS)
        modify_fn(config)
        runner = SimulationRunner(config)
        raw = runner.run(days=DAYS, seed=seed)
        metrics = extract_metrics(raw)
        metrics["seed"] = seed
        results.append(metrics)
    return results


def compute_stats(results: list[dict], keys: list[str]) -> dict:
    import statistics
    stats = {}
    for key in keys:
        values = [r[key] for r in results]
        stats[key] = {
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
        }
    return stats


def format_table(on_stats: dict, off_stats: dict, keys: list[str], labels: dict) -> str:
    lines = []
    lines.append(f"  {'Metric':<25} {'ON (mean±sd)':<22} {'OFF (mean±sd)':<22} {'Delta':<12} {'Effect'}")
    lines.append(f"  {'─' * 25} {'─' * 22} {'─' * 22} {'─' * 12} {'─' * 10}")

    for key in keys:
        on = on_stats[key]
        off = off_stats[key]
        delta = on["mean"] - off["mean"]
        pct = (delta / off["mean"] * 100) if off["mean"] != 0 else float("inf") if delta > 0 else 0

        on_str = f"{on['mean']:.3f} ± {on['stdev']:.3f}"
        off_str = f"{off['mean']:.3f} ± {off['stdev']:.3f}"
        delta_str = f"{delta:+.3f}"

        if abs(pct) > 20:
            effect = "███ STRONG"
        elif abs(pct) > 10:
            effect = "██ MODERATE"
        elif abs(pct) > 5:
            effect = "█ WEAK"
        else:
            effect = "~ NEGLIGIBLE"

        if delta < 0 and pct < -10:
            effect = "▼ HARMFUL"

        lines.append(f"  {labels.get(key, key):<25} {on_str:<22} {off_str:<22} {delta_str:<12} {effect}")

    return "\n".join(lines)


print("=" * 90)
print("  ARIA WORLD — CONTROLLED ABLATION STUDY")
print("=" * 90)
print(f"\n  Configuration: {DAYS} days, {AGENTS} agents, {RUNS} runs per condition")
print(f"  Seeds: {SEEDS}")
print()

METRIC_KEYS = [
    "survival_rate", "final_population", "total_births",
    "knowledge_total", "knowledge_avg_level",
    "teachings_total", "teachings_successful",
    "experts", "recipes", "innovations",
    "average_happiness",
]

LABELS = {
    "survival_rate": "Survival Rate",
    "final_population": "Final Population",
    "total_births": "Total Births",
    "knowledge_total": "Knowledge Entries",
    "knowledge_avg_level": "Avg Knowledge Level",
    "teachings_total": "Total Teachings",
    "teachings_successful": "Successful Teachings",
    "experts": "Expert Agents",
    "recipes": "Recipes Discovered",
    "innovations": "Innovations Made",
    "average_happiness": "Average Happiness",
}

# ── Experiment 1: Reflection ──
print("=" * 90)
print("  EXPERIMENT 1: REFLECTION ABLATION")
print("  Does reflecting on outcomes improve survival and learning?")
print("=" * 90)

on_results = run_condition("reflection_on", lambda c: None, SEEDS)
off_results = run_condition("reflection_off", lambda c: setattr(c, '_disable_reflection', True), SEEDS)
on_stats = compute_stats(on_results, METRIC_KEYS)
off_stats = compute_stats(off_results, METRIC_KEYS)
print(format_table(on_stats, off_stats, METRIC_KEYS, LABELS))

# ── Experiment 2: Memory ──
print("\n" + "=" * 90)
print("  EXPERIMENT 2: MEMORY ABLATION")
print("  Does episodic memory improve planning and knowledge retention?")
print("=" * 90)

on_results = run_condition("memory_on", lambda c: None, SEEDS)
off_results = run_condition("memory_off", lambda c: setattr(c, '_disable_memory', True), SEEDS)
on_stats = compute_stats(on_results, METRIC_KEYS)
off_stats = compute_stats(off_results, METRIC_KEYS)
print(format_table(on_stats, off_stats, METRIC_KEYS, LABELS))

# ── Experiment 3: Trust ──
print("\n" + "=" * 90)
print("  EXPERIMENT 3: TRUST ABLATION")
print("  Does trust-based teaching transfer knowledge between agents?")
print("=" * 90)

on_results = run_condition("trust_on", lambda c: None, SEEDS)
off_results = run_condition("trust_off", lambda c: setattr(c, '_disable_trust', True), SEEDS)
on_stats = compute_stats(on_results, METRIC_KEYS)
off_stats = compute_stats(off_results, METRIC_KEYS)
print(format_table(on_stats, off_stats, METRIC_KEYS, LABELS))

# ── Experiment 4: Curiosity ──
print("\n" + "=" * 90)
print("  EXPERIMENT 4: CURIOSITY ABLATION")
print("  Does curiosity drive innovation and recipe discovery?")
print("=" * 90)

on_results = run_condition("curiosity_on", lambda c: None, SEEDS)
off_results = run_condition("curiosity_off", lambda c: setattr(c, '_disable_curiosity', True), SEEDS)
on_stats = compute_stats(on_results, METRIC_KEYS)
off_stats = compute_stats(off_results, METRIC_KEYS)
print(format_table(on_stats, off_stats, METRIC_KEYS, LABELS))

# ── Summary ──
print("\n" + "=" * 90)
print("  SUMMARY: WHICH COMPONENTS MATTER?")
print("=" * 90)
print("""
  Component       Survival  Knowledge  Innovation  Teaching   Verdict
  ─────────────── ───────── ────────── ─────────── ────────── ────────
  Reflection      See Exp 1 ─────────────────────────────────────────
  Memory          See Exp 2 ─────────────────────────────────────────
  Trust           See Exp 3 ─────────────────────────────────────────
  Curiosity       See Exp 4 ─────────────────────────────────────────

  A component MATTERS if removing it causes >10% degradation in any metric.
  A component is CRITICAL if removing it causes >20% degradation.
  A component is NEGLIGIBLE if removing it causes <5% change.
""")
