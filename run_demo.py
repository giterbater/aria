"""Demo script to run ARIA World simulation."""
import sys
sys.path.insert(0, '.')

from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner

config = SimulationConfig(seed=42, initial_agents=10, max_days=30)
runner = SimulationRunner(config)
result = runner.run(days=30, seed=42)

print("=== ARIA World Simulation Results ===")
print("Days Run:", result["days_run"])
print("Initial Population:", result["initial_population"])
print("Final Population:", result["final_population"])
print("Survival Rate: {:.1%}".format(result["survival_rate"]))
print("Average Happiness: {:.2f}".format(result["average_happiness"]))
print("Average Lifespan: {:.1f} days".format(result["average_lifespan_days"]))
print("Average Knowledge: {:.1f}".format(result["average_knowledge"]))
print("Total Births:", result["total_births"])
print("Total Conflicts:", result["total_conflicts"])
print()

bench = runner.benchmark(days=30, seed=42)
ms = bench["metric_set"]
print("=== Benchmark Metrics ===")
for m in ms.metrics:
    print("  {}: {:.3f}".format(m.name, m.value))
print("  Overall Score: {:.3f}".format(ms.overall_score()))
