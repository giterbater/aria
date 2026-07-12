"""Demo script to run ARIA World simulation with new systems."""
import sys
sys.path.insert(0, '.')

from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner

config = SimulationConfig(seed=42, initial_agents=10, max_days=50)
runner = SimulationRunner(config)
result = runner.run(days=50, seed=42)

print("=== ARIA World Simulation Results (50 days) ===")
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

print("=== Knowledge System ===")
ks = result.get("knowledge_stats", {})
print("Total Knowledge Entries:", ks.get("total", 0))
print("Average Level: {:.2f}".format(ks.get("average_level", 0)))
print("Total Teachings:", ks.get("total_teachings", 0))
print("Successful Teachings:", ks.get("successful_teachings", 0))
print()

print("=== Expertise System ===")
es = result.get("expertise_stats", {})
print("Total Skill Profiles:", es.get("total_profiles", 0))
print("Expert Agents:", es.get("experts", 0))
by_skill = es.get("by_skill", {})
for skill, stats in by_skill.items():
    print("  {}: {} agents, avg level {:.2f}".format(skill, stats["count"], stats["avg_level"]))
print()

print("=== Culture System ===")
cs = result.get("culture_stats", {})
print("Total Customs:", cs.get("total_customs", 0))
print("Active Customs:", cs.get("active_customs", 0))
print("Strong Customs:", cs.get("strong_customs", 0))
print("Total Strategies:", cs.get("total_strategies", 0))
print("Proven Strategies:", cs.get("proven_strategies", 0))
print("Village Knowledge:", cs.get("village_knowledge_count", 0))
print()

print("=== Innovation System ===")
is_ = result.get("innovation_stats", {})
print("Total Recipes:", is_.get("total_recipes", 0))
print("Total Innovations:", is_.get("total_innovations", 0))
print("Recipes Used:", is_.get("recipes_used", 0))
print("Average Efficiency: {:.2f}".format(is_.get("average_efficiency", 0)))
print()

bench = runner.benchmark(days=50, seed=42)
ms = bench["metric_set"]
print("=== Benchmark Metrics ===")
for m in ms.metrics:
    print("  {}: {:.3f}".format(m.name, m.value))
print("  Overall Score: {:.3f}".format(ms.overall_score()))
