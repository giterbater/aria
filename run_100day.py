"""Run 100-day ARIA World simulation with visualization."""
import sys
sys.path.insert(0, '.')

from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner
from aria_world.visualization import SimulationVisualizer

print("Initializing ARIA World...")
config = SimulationConfig(seed=42, initial_agents=15, max_days=100)
runner = SimulationRunner(config)

print("Running 100-day simulation...")
result = runner.run(days=100, seed=42)

print("Generating visualization report...")
viz = SimulationVisualizer(result)
report = viz.full_report()
print(report)

print("\n\n" + "=" * 70)
print("  BENCHMARK SCORES")
print("=" * 70)
bench = runner.benchmark(days=100, seed=42)
ms = bench["metric_set"]
for m in ms.metrics:
    bar_len = int(m.value * 40)
    bar = "█" * bar_len + "░" * (40 - bar_len)
    print(f"  {m.name:<30} |{bar}| {m.value:.3f}")
print(f"\n  {'OVERALL SCORE':<30} |{'█' * int(ms.overall_score() * 40)}{'░' * (40 - int(ms.overall_score() * 40))}| {ms.overall_score():.3f}")
