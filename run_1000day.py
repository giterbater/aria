"""Run 1000-day ARIA World simulation — full research run."""
import sys
sys.path.insert(0, '.')

from aria_world.config import SimulationConfig
from aria_world.runner import SimulationRunner
from aria_world.visualization import SimulationVisualizer

print("Initializing ARIA World...")
config = SimulationConfig(seed=42, initial_agents=20, max_days=1000)
runner = SimulationRunner(config)

print("Running 1000-day simulation (this may take a minute)...")
result = runner.run(days=1000, seed=42)

print("\n\n" + "=" * 70)
print("  ARIA WORLD — 1000-DAY RESEARCH SIMULATION")
print("=" * 70)

viz = SimulationVisualizer(result)
report = viz.full_report()
print(report)

print("\n\n" + "=" * 70)
print("  RESEARCH OBSERVATIONS")
print("=" * 70)

# Compute observations
daily = result.get("daily_results", [])
pop_history = [d.get("alive_count", 0) for d in daily]
births_total = result.get("total_births", 0)
deaths_total = len(daily) * result.get("initial_population", 0) - sum(pop_history) if pop_history else 0
ks = result.get("knowledge_stats", {})
es = result.get("expertise_stats", {})
is_ = result.get("innovation_stats", {})
cs = result.get("culture_stats", {})

# Compute death rate per phase
phase1 = pop_history[:250] if len(pop_history) >= 250 else pop_history
phase2 = pop_history[250:500] if len(pop_history) >= 500 else []
phase3 = pop_history[500:750] if len(pop_history) >= 750 else []
phase4 = pop_history[750:] if len(pop_history) >= 750 else []

def avg_pop(phase):
    return sum(phase) / len(phase) if phase else 0

def pop_trend(phase):
    if len(phase) < 2:
        return "stable"
    first_half = sum(phase[:len(phase)//2]) / (len(phase)//2)
    second_half = sum(phase[len(phase)//2:]) / (len(phase) - len(phase)//2)
    if second_half > first_half * 1.1:
        return "growing"
    elif second_half < first_half * 0.9:
        return "declining"
    return "stable"

print(f"""
  1. POPULATION DYNAMICS
     Initial: {result.get("initial_population", 0)}
     Final: {result.get("final_population", 0)}
     Peak: {max(pop_history) if pop_history else 0}
     Trough: {min(pop_history) if pop_history else 0}
     Births: {births_total}

     Phase Analysis:
       Days 1-250:    avg {avg_pop(phase1):.1f} agents, {pop_trend(phase1)}
       Days 251-500:  avg {avg_pop(phase2):.1f} agents, {pop_trend(phase2)}
       Days 501-750:  avg {avg_pop(phase3):.1f} agents, {pop_trend(phase3)}
       Days 751-1000: avg {avg_pop(phase4):.1f} agents, {pop_trend(phase4)}

  2. KNOWLEDGE ACCUMULATION
     Total entries: {ks.get("total", 0)}
     Average level: {ks.get("average_level", 0):.3f}
     Teachings: {ks.get("total_teachings", 0)} ({ks.get("successful_teachings", 0)} successful)
     Teaching success rate: {ks.get("successful_teachings", 0) / max(ks.get("total_teachings", 1), 1):.0%}

     Knowledge per day: {ks.get("total", 0) / max(len(daily), 1):.2f}
     Teaching per day: {ks.get("total_teachings", 0) / max(len(daily), 1):.2f}

  3. EXPERTISE DEVELOPMENT
     Total profiles: {es.get("total_profiles", 0)}
     Expert agents: {es.get("experts", 0)}
     Expertise rate: {es.get("experts", 0) / max(result.get("final_population", 1), 1):.0%}

     By skill:""")
for skill, stats in sorted(es.get("by_skill", {}).items()):
    print(f"       {skill:<15} {stats['count']:>3} agents, avg {stats['avg_level']:.2f}")

print(f"""
  4. INNOVATION & TECHNOLOGY
     Recipes: {is_.get("total_recipes", 0)}
     Innovations: {is_.get("total_innovations", 0)}
     Efficiency: {is_.get("average_efficiency", 0):.2f}
     Innovation per day: {is_.get("total_innovations", 0) / max(len(daily), 1):.4f}

  5. CULTURE FORMATION
     Customs: {cs.get("total_customs", 0)} (active: {cs.get("active_customs", 0)})
     Strategies: {cs.get("total_strategies", 0)} (proven: {cs.get("proven_strategies", 0)})
     Village knowledge: {cs.get("village_knowledge_count", 0)}

  6. EMERGENT BEHAVIOR ANALYSIS""")
print(f"     Population stability: {'STABLE' if pop_trend(phase4) == 'stable' else 'UNSTABLE'}")
print(f"     Knowledge growth: {'LINEAR' if ks.get('total', 0) > len(daily) * 0.5 else 'SUBLINEAR'}")
print(f"     Expertise concentration: {'HIGH' if es.get('experts', 0) > result.get('final_population', 1) * 0.5 else 'LOW'}")
print(f"     Innovation rate: {'ACTIVE' if is_.get('total_innovations', 0) > 5 else 'EMERGING' if is_.get('total_innovations', 0) > 0 else 'DORMANT'}")

# Detect crises
crises = []
for i in range(1, len(pop_history)):
    if pop_history[i] < pop_history[i-1] * 0.7:
        crises.append((i+1, pop_history[i-1], pop_history[i]))
print(f"\n  7. CRISIS EVENTS (population drop > 30%)")
if crises:
    for day, before, after in crises[:5]:
        print(f"       Day {day}: {before} → {after} ({(after-before)/before:.0%} drop)")
else:
    print("       No major crises detected")

print(f"""
  8. LONG-TERM TRAJECTORY
     The village {"survived" if result.get("final_population", 0) > 0 else "collapsed"} over 1000 days.
     Net population change: {result.get("final_population", 0) - result.get("initial_population", 0):+d}
     {"Knowledge is compounding" if ks.get("total", 0) > 50 else "Knowledge accumulation is slow"}.
     {"Expertise is widespread" if es.get("experts", 0) > 5 else "Expertise is concentrated"}.
     {"Culture is forming" if cs.get("total_customs", 0) > 0 else "Culture has not emerged yet"}.

  9. WHAT THIS MEASURES
     - Survival capability under resource constraints
     - Knowledge transfer efficiency (trust → teaching → mastery)
     - Innovation rate (curiosity → discovery → new recipes)
     - Social cohesion (trust network, trade, conflict resolution)
     - Reproductive success (population sustainability)
     - Adaptive capacity (response to events, replanning)

  10. NEXT STEPS
      - Add more event types (disease, migration, alliances)
      - Implement inter-village trade and warfare
      - Add language evolution
      - Measure cognitive load per agent
      - Compare ARIA v1 vs v2 performance
""")

# Final benchmark
print("=" * 70)
print("  FINAL BENCHMARK SCORES")
print("=" * 70)
bench = runner.benchmark(days=1000, seed=42)
ms = bench["metric_set"]
for m in ms.metrics:
    bar_len = int(m.value * 40)
    bar = "█" * bar_len + "░" * (40 - bar_len)
    print(f"  {m.name:<30} |{bar}| {m.value:.3f}")
print(f"\n  {'OVERALL SCORE':<30} |{'█' * int(ms.overall_score() * 40)}{'░' * (40 - int(ms.overall_score() * 40))}| {ms.overall_score():.3f}")
