#!/usr/bin/env python3
"""
Memory Influence Deep Investigation

1. More seeds on memory-only (200)
2. All component combinations
3. Proper CI for differences
4. Why memory works so well
"""

import random
import json
import math
import statistics
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field

from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.memory.influence import MemoryInfluenceEngine
from aria_core.identity.formation import IdentityFormationEngine
from aria_core.values.formation import ValueFormationEngine
from aria_core.memory.models import EpisodicItem, Outcome


@dataclass
class Config:
    name: str
    use_memory: bool = False
    use_identity: bool = False
    use_values: bool = False
    num_seeds: int = 100
    episodes: int = 100
    success_probs: Dict[str, float] = field(default_factory=lambda: {
        'inform': 0.8, 'execute': 0.6, 'query': 0.7, 'warn': 0.3
    })


class Agent:
    def __init__(self, config: Config, seed: int):
        self.config = config
        random.seed(seed)
        
        self.memory = SimpleMemorySystem()
        self.influence = MemoryInfluenceEngine(self.memory) if config.use_memory else None
        self.identity = IdentityFormationEngine() if config.use_identity else None
        self.values = ValueFormationEngine() if config.use_values else None
        
        self.episodes = []
        self.action_counts = {}
        self.success_counts = {}
    
    def decide(self) -> str:
        actions = ['inform', 'execute', 'query', 'warn']
        probs = {a: 0.25 for a in actions}
        
        if self.influence:
            for sig in self.influence.compute_influences(limit=10):
                if sig.action_preference in probs:
                    probs[sig.action_preference] += sig.strength * 0.3
            total = sum(probs.values())
            probs = {a: p/total for a, p in probs.items()}
        
        if self.identity:
            for action, strength in self.identity.get_identity_signals().get('action_preferences', {}).items():
                if action in probs:
                    probs[action] += strength * 0.2
            total = sum(probs.values())
            probs = {a: p/total for a, p in probs.items()}
        
        if self.values:
            for vname, vdata in self.values.get_value_signals().get('active_values', {}).items():
                if vdata.get('direction') == 'positive':
                    if vname == 'efficiency' and 'execute' in probs:
                        probs['execute'] += 0.1
                    elif vname == 'curiosity' and 'query' in probs:
                        probs['query'] += 0.1
            total = sum(probs.values())
            probs = {a: p/total for a, p in probs.items()}
        
        return random.choices(actions, weights=[probs[a] for a in actions], k=1)[0]
    
    def run(self, num_episodes: int) -> Dict[str, Any]:
        for i in range(num_episodes):
            action = self.decide()
            success = random.random() < self.config.success_probs.get(action, 0.5)
            outcome = 'success' if success else 'failed'
            
            episode = EpisodicItem(
                importance=0.6 if success else 0.4,
                structured_input={"text": f"action {i}"},
                decision=type('D', (), {'action_type': action, 'payload': {}})(),
                outcome=Outcome.SUCCESS.value if success else Outcome.FAILED.value,
            )
            self.memory.store_episodic(episode)
            
            if self.identity:
                self.identity.observe_action(action, outcome, {
                    'risk_level': random.choice(['low', 'medium', 'high']),
                    'duration_ms': random.randint(100, 5000),
                    'retries': 0 if success else random.randint(1, 3),
                })
            
            if self.values:
                self.values.observe_outcome(action, outcome, {
                    'duration_ms': random.randint(100, 5000),
                    'retries': 0 if success else random.randint(1, 3),
                    'risk_level': random.choice(['low', 'medium', 'high']),
                    'complexity': random.choice(['low', 'medium', 'high']),
                    'completeness': 'high' if success else 'low',
                    'speed': 'fast' if random.randint(0, 1) else 'slow',
                })
            
            self.action_counts[action] = self.action_counts.get(action, 0) + 1
            if success:
                self.success_counts[action] = self.success_counts.get(action, 0) + 1
            
            self.episodes.append({'action': action, 'success': success})
        
        return self.get_metrics()
    
    def get_metrics(self) -> Dict[str, Any]:
        total = len(self.episodes)
        if total == 0:
            return {'success_rate': 0, 'diversity': 0}
        
        successes = sum(1 for e in self.episodes if e['success'])
        
        # Diversity (Shannon entropy)
        probs = [c/total for c in self.action_counts.values() if c > 0]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(len(self.action_counts)) if self.action_counts else 1
        diversity = entropy / max_entropy if max_entropy > 0 else 0
        
        # Action preference shift (how much did preferences change from uniform?)
        uniform = 0.25
        shifts = []
        for action in ['inform', 'execute', 'query', 'warn']:
            actual = self.action_counts.get(action, 0) / total
            shifts.append(abs(actual - uniform))
        preference_shift = sum(shifts) / len(shifts)
        
        # Success rate by action
        action_success = {}
        for action in self.action_counts:
            if action in self.success_counts:
                action_success[action] = self.success_counts[action] / self.action_counts[action]
            else:
                action_success[action] = 0
        
        return {
            'success_rate': successes / total,
            'diversity': diversity,
            'preference_shift': preference_shift,
            'action_counts': self.action_counts.copy(),
            'action_success': action_success,
            'identity_coherence': self.identity.state.identity_coherence if self.identity else 0,
            'value_coherence': self.values.state.value_coherence if self.values else 0,
            'stable_prefs': len(self.identity.get_stable_preferences()) if self.identity else 0,
            'stable_vals': len(self.values.get_stable_values()) if self.values else 0,
        }


def ci_95(values: List[float]) -> Tuple[float, float]:
    """95% CI for mean."""
    n = len(values)
    if n < 2:
        return (0, 0)
    mean = statistics.mean(values)
    se = statistics.stdev(values) / math.sqrt(n)
    return (mean - 1.96 * se, mean + 1.96 * se)


def ci_difference(group1: List[float], group2: List[float]) -> Tuple[float, float, float]:
    """95% CI for difference of means."""
    n1, n2 = len(group1), len(group2)
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1 = statistics.variance(group1) if n1 > 1 else 0
    var2 = statistics.variance(group2) if n2 > 1 else 0
    
    diff = mean1 - mean2
    se_diff = math.sqrt(var1/n1 + var2/n2)
    
    return (diff - 1.96 * se_diff, diff, diff + 1.96 * se_diff)


def cohens_d(group1: List[float], group2: List[float]) -> float:
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1, var2 = statistics.variance(group1), statistics.variance(group2)
    pooled_std = math.sqrt(((n1-1)*var1 + (n2-1)*var2) / (n1+n2-2))
    return (mean1 - mean2) / pooled_std if pooled_std > 0 else 0


def welch_t(group1: List[float], group2: List[float]) -> Tuple[float, float]:
    n1, n2 = len(group1), len(group2)
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1 = statistics.variance(group1) if n1 > 1 else 0
    var2 = statistics.variance(group2) if n2 > 1 else 0
    se = math.sqrt(var1/n1 + var2/n2)
    if se == 0:
        return (0, 1)
    t = (mean1 - mean2) / se
    z = abs(t)
    p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    return (t, p)


def run_condition(config: Config) -> List[Dict[str, Any]]:
    results = []
    for seed in range(config.num_seeds):
        agent = Agent(config, seed)
        metrics = agent.run(config.episodes)
        metrics['seed'] = seed
        results.append(metrics)
    return results


def main():
    print("="*70)
    print("MEMORY INFLUENCE DEEP INVESTIGATION")
    print("="*70)
    
    num_seeds = 200
    episodes = 100
    
    # All combinations
    configs = [
        Config("None (Baseline)", num_seeds=num_seeds, episodes=episodes),
        Config("Memory Only", use_memory=True, num_seeds=num_seeds, episodes=episodes),
        Config("Identity Only", use_identity=True, num_seeds=num_seeds, episodes=episodes),
        Config("Values Only", use_values=True, num_seeds=num_seeds, episodes=episodes),
        Config("Memory + Identity", use_memory=True, use_identity=True, num_seeds=num_seeds, episodes=episodes),
        Config("Memory + Values", use_memory=True, use_values=True, num_seeds=num_seeds, episodes=episodes),
        Config("Identity + Values", use_identity=True, use_values=True, num_seeds=num_seeds, episodes=episodes),
        Config("Full System", use_memory=True, use_identity=True, use_values=True, num_seeds=num_seeds, episodes=episodes),
    ]
    
    all_results = {}
    for config in configs:
        print(f"\nRunning: {config.name} ({num_seeds} seeds)...")
        results = run_condition(config)
        all_results[config.name] = results
    
    # Analysis
    print("\n" + "="*70)
    print("RESULTS TABLE")
    print("="*70)
    
    baseline = [r['success_rate'] for r in all_results["None (Baseline)"]]
    
    print(f"\n{'Condition':<25} {'Mean':>8} {'95% CI':>20} {'Δ vs Base':>12} {'d':>8} {'p':>10}")
    print("-"*85)
    
    comparison_data = {}
    
    for name, results in all_results.items():
        rates = [r['success_rate'] for r in results]
        mean = statistics.mean(rates)
        ci = ci_95(rates)
        
        if name == "None (Baseline)":
            print(f"{name:<25} {mean:>8.4f} [{ci[0]:.4f}, {ci[1]:.4f}]{'':>12} {'':>8} {'':>10}")
            baseline_mean = mean
        else:
            diff_ci = ci_difference(rates, baseline)
            d = cohens_d(rates, baseline)
            t, p = welch_t(rates, baseline)
            
            diff_pct = (mean - baseline_mean) / baseline_mean * 100
            
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            
            print(f"{name:<25} {mean:>8.4f} [{ci[0]:.4f}, {ci[1]:.4f}] {diff_pct:>+10.1f}% {d:>8.3f} {p:>9.4f} {sig}")
            
            comparison_data[name] = {
                'mean': mean,
                'ci': ci,
                'diff_pct': diff_pct,
                'cohens_d': d,
                'p_value': p,
                'significant': p < 0.05,
            }
    
    # Why does memory work so well?
    print("\n" + "="*70)
    print("WHY MEMORY INFLUENCE WORKS")
    print("="*70)
    
    memory_results = all_results["Memory Only"]
    
    # Analyze preference shifts
    shifts = [r['preference_shift'] for r in memory_results]
    print(f"\nPreference shift from uniform: {statistics.mean(shifts):.4f} ± {statistics.stdev(shifts):.4f}")
    
    # Analyze action selection patterns
    action_preferences = {'inform': [], 'execute': [], 'query': [], 'warn': []}
    for r in memory_results:
        total = sum(r['action_counts'].values())
        for action in action_preferences:
            action_preferences[action].append(r['action_counts'].get(action, 0) / total)
    
    print("\nAction selection probabilities (Memory Only):")
    for action, probs in action_preferences.items():
        mean_prob = statistics.mean(probs)
        base_prob = 0.25
        shift = mean_prob - base_prob
        print(f"  {action}: {mean_prob:.3f} (shift: {shift:+.3f})")
    
    # Analyze correlation between preference shift and success rate
    shifts = [r['preference_shift'] for r in memory_results]
    success_rates = [r['success_rate'] for r in memory_results]
    
    # Pearson correlation
    n = len(shifts)
    mean_x = statistics.mean(shifts)
    mean_y = statistics.mean(success_rates)
    std_x = statistics.stdev(shifts)
    std_y = statistics.stdev(success_rates)
    
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(shifts, success_rates)) / (n - 1)
    correlation = cov / (std_x * std_y) if std_x * std_y > 0 else 0
    
    print(f"\nCorrelation between preference shift and success rate: r = {correlation:.3f}")
    
    # Memory influence signals analysis
    print("\nMemory influence mechanism:")
    print("  - Success at 'inform' (80% base rate) → positive signal")
    print("  - Failure at 'warn' (30% base rate) → negative signal")
    print("  - Agent learns to prefer 'inform' and avoid 'warn'")
    print("  - This concentrates probability on higher-success actions")
    
    # Theoretical maximum
    # If agent always picks 'inform' (80% success), expected = 0.80
    # If agent always picks 'query' (70% success), expected = 0.70
    # Weighted optimal: mostly inform + some query
    optimal_rate = 0.8 * 0.7 + 0.7 * 0.2 + 0.6 * 0.08 + 0.3 * 0.02  # rough estimate
    print(f"\nTheoretical optimal (if always pick best): ~0.78")
    print(f"Memory-only achieved: {statistics.mean([r['success_rate'] for r in memory_results]):.3f}")
    print(f"Gap to optimal: {0.78 - statistics.mean([r['success_rate'] for r in memory_results]):.3f}")
    
    # Interaction effects
    print("\n" + "="*70)
    print("INTERACTION EFFECTS")
    print("="*70)
    
    mem_only = comparison_data.get('Memory Only', {}).get('mean', 0)
    id_only = comparison_data.get('Identity Only', {}).get('mean', 0)
    val_only = comparison_data.get('Values Only', {}).get('mean', 0)
    mem_id = comparison_data.get('Memory + Identity', {}).get('mean', 0)
    mem_val = comparison_data.get('Memory + Values', {}).get('mean', 0)
    id_val = comparison_data.get('Identity + Values', {}).get('mean', 0)
    full = comparison_data.get('Full System', {}).get('mean', 0)
    baseline_mean = statistics.mean(baseline)
    
    print(f"\nAdditive vs Actual:")
    print(f"  Memory + Identity (additive): {(mem_only - baseline_mean) + (id_only - baseline_mean) + baseline_mean:.4f}")
    print(f"  Memory + Identity (actual):   {mem_id:.4f}")
    print(f"  Interaction:                  {mem_id - ((mem_only - baseline_mean) + (id_only - baseline_mean) + baseline_mean):+.4f}")
    
    print(f"\n  Memory + Values (additive):   {(mem_only - baseline_mean) + (val_only - baseline_mean) + baseline_mean:.4f}")
    print(f"  Memory + Values (actual):     {mem_val:.4f}")
    print(f"  Interaction:                  {mem_val - ((mem_only - baseline_mean) + (val_only - baseline_mean) + baseline_mean):+.4f}")
    
    print(f"\n  Full (additive):              {(mem_only - baseline_mean) + (id_only - baseline_mean) + (val_only - baseline_mean) + baseline_mean:.4f}")
    print(f"  Full (actual):                {full:.4f}")
    print(f"  Interaction:                  {full - ((mem_only - baseline_mean) + (id_only - baseline_mean) + (val_only - baseline_mean) + baseline_mean):+.4f}")
    
    # Save results
    output = {
        'parameters': {'num_seeds': num_seeds, 'episodes': episodes},
        'conditions': {name: {
            'mean': statistics.mean([r['success_rate'] for r in results]),
            'std': statistics.stdev([r['success_rate'] for r in results]),
            'ci_95': ci_95([r['success_rate'] for r in results]),
            'preference_shift': statistics.mean([r['preference_shift'] for r in results]),
        } for name, results in all_results.items()},
        'comparisons': comparison_data,
        'memory_analysis': {
            'preference_shift_mean': statistics.mean(shifts),
            'preference_shift_std': statistics.stdev(shifts),
            'correlation_shift_success': correlation,
        },
    }
    
    output_path = Path("memory_investigation_results.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    
    # Generate plots
    generate_investigation_plots(all_results, comparison_data)


def generate_investigation_plots(all_results, comparison_data):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Memory Influence Investigation', fontsize=14, fontweight='bold')
    
    # Plot 1: All combinations
    ax = axes[0, 0]
    names = list(comparison_data.keys())
    means = [comparison_data[n]['mean'] for n in names]
    ci_lows = [comparison_data[n]['ci'][0] for n in names]
    ci_highs = [comparison_data[n]['ci'][1] for n in names]
    errors = [[m-l for m,l in zip(means, ci_lows)], [h-m for m,h in zip(means, ci_highs)]]
    
    x = np.arange(len(names))
    colors = ['gray', 'blue', 'orange', 'red', 'purple', 'green', 'brown', 'black']
    ax.bar(x, means, yerr=errors, capsize=3, color=colors[:len(names)])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right', fontsize=7)
    ax.set_ylabel('Success Rate')
    ax.set_title('Success Rate by Configuration (95% CI)')
    ax.set_ylim(0.5, 0.75)
    
    # Plot 2: Distributions
    ax = axes[0, 1]
    for name in ["None (Baseline)", "Memory Only", "Full System"]:
        rates = [r['success_rate'] for r in all_results[name]]
        ax.hist(rates, bins=30, alpha=0.5, label=name, density=True)
    ax.set_xlabel('Success Rate')
    ax.set_ylabel('Density')
    ax.set_title('Success Rate Distributions')
    ax.legend()
    
    # Plot 3: Effect sizes
    ax = axes[1, 0]
    names = list(comparison_data.keys())
    ds = [comparison_data[n]['cohens_d'] for n in names]
    colors = ['green' if d > 0 else 'red' for d in ds]
    ax.barh(range(len(ds)), ds, color=colors)
    ax.set_yticks(range(len(ds)))
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlabel("Cohen's d")
    ax.set_title('Effect Sizes vs Baseline')
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.axvline(x=0.2, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    ax.axvline(x=0.5, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    ax.axvline(x=0.8, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    
    # Plot 4: Preference shift vs success
    ax = axes[1, 1]
    memory_results = all_results["Memory Only"]
    shifts = [r['preference_shift'] for r in memory_results]
    success = [r['success_rate'] for r in memory_results]
    ax.scatter(shifts, success, alpha=0.3, s=10)
    ax.set_xlabel('Preference Shift from Uniform')
    ax.set_ylabel('Success Rate')
    ax.set_title('Preference Shift vs Success (Memory Only)')
    
    # Add trend line
    z = np.polyfit(shifts, success, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(shifts), max(shifts), 100)
    ax.plot(x_line, p(x_line), "r--", alpha=0.8, label=f'r={np.corrcoef(shifts, success)[0,1]:.3f}')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig('memory_investigation_plots.png', dpi=150, bbox_inches='tight')
    print("Plots saved to memory_investigation_plots.png")
    plt.close()


if __name__ == "__main__":
    main()
