#!/usr/bin/env python3
"""
Rigorous Developmental Cognition Experiment

100+ seeds, statistical tests, confidence intervals, ablation studies.
Paper-quality experimental methodology.
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
class ExperimentConfig:
    """Configuration for a single experiment."""
    name: str
    use_memory_influence: bool = True
    use_identity: bool = True
    use_values: bool = True
    use_reflection: bool = True
    num_seeds: int = 100
    episodes_per_seed: int = 100
    # Environment parameters
    success_probs: Dict[str, float] = field(default_factory=lambda: {
        'inform': 0.8, 'execute': 0.6, 'query': 0.7, 'warn': 0.3
    })
    # Stress test parameters
    catastrophic_event_prob: float = 0.0
    resource_scarcity: float = 0.0
    population_size: int = 1


@dataclass
class SeedResult:
    """Result from a single seed run."""
    seed: int
    success_rate: float
    action_diversity: float
    behavioral_consistency: float
    action_counts: Dict[str, int]
    success_counts: Dict[str, int]
    identity_coherence: float
    value_coherence: float
    stable_preferences: int
    stable_values: int
    # Stress test metrics
    catastrophes_survived: int = 0
    resource_efficiency: float = 0.0


class AgentSimulator:
    """Simulates an agent with configurable developmental components."""
    
    def __init__(self, config: ExperimentConfig, seed: int):
        self.config = config
        self.seed = seed
        random.seed(seed)
        
        self.memory = SimpleMemorySystem()
        self.influence = MemoryInfluenceEngine(self.memory) if config.use_memory_influence else None
        self.identity = IdentityFormationEngine() if config.use_identity else None
        self.values = ValueFormationEngine() if config.use_values else None
        
        self.episodes: List[Dict[str, Any]] = []
        self.action_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        self.resources = 100.0
        self.catastrophes_survived = 0
    
    def decide(self) -> str:
        """Make a decision based on current state."""
        action_types = ['inform', 'execute', 'query', 'warn']
        probs = {a: 0.25 for a in action_types}
        
        # Apply memory influence
        if self.influence is not None:
            signals = self.influence.compute_influences(limit=10)
            for signal in signals:
                if signal.action_preference in probs:
                    probs[signal.action_preference] += signal.strength * 0.3
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Apply identity preferences
        if self.identity is not None:
            identity_signals = self.identity.get_identity_signals()
            for action, strength in identity_signals.get('action_preferences', {}).items():
                if action in probs:
                    probs[action] += strength * 0.2
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Apply value preferences
        if self.values is not None:
            value_signals = self.values.get_value_signals()
            for value_name, value_data in value_signals.get('active_values', {}).items():
                if value_data.get('direction') == 'positive':
                    if value_name == 'efficiency' and 'execute' in probs:
                        probs['execute'] += 0.1
                    elif value_name == 'curiosity' and 'query' in probs:
                        probs['query'] += 0.1
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Handle resource scarcity
        if self.config.resource_scarcity > 0:
            if self.resources < 20:
                # Desperation: prefer actions that might produce resources
                probs['execute'] += 0.2
                probs['warn'] += 0.1
                total = sum(probs.values())
                probs = {a: p / total for a, p in probs.items()}
        
        actions = list(probs.keys())
        weights = list(probs.values())
        return random.choices(actions, weights=weights, k=1)[0]
    
    def simulate_episode(self, cycle: int) -> SeedResult:
        """Simulate one episode."""
        # Check for catastrophic event
        if random.random() < self.config.catastrophic_event_prob:
            self.resources *= 0.5
            self.catastrophes_survived += 1
        
        # Make decision
        action = self.decide()
        
        # Determine outcome
        success_probs = self.config.success_probs.copy()
        
        # Modify success probability based on resources
        if self.resources < 30:
            success_probs = {k: v * 0.7 for k, v in success_probs.items()}
        
        success = random.random() < success_probs.get(action, 0.5)
        outcome = 'success' if success else 'failed'
        
        # Update resources
        if success:
            self.resources = min(100, self.resources + 5)
        else:
            self.resources = max(0, self.resources - 3)
        
        # Record in memory
        episode = EpisodicItem(
            importance=0.6 if success else 0.4,
            structured_input={"text": f"action {cycle}"},
            decision=type('Decision', (), {'action_type': action, 'payload': {}})(),
            outcome=Outcome.SUCCESS.value if success else Outcome.FAILED.value,
        )
        self.memory.store_episodic(episode)
        
        # Update developmental components
        if self.identity is not None:
            self.identity.observe_action(
                action_type=action,
                outcome=outcome,
                context={
                    'risk_level': random.choice(['low', 'medium', 'high']),
                    'duration_ms': random.randint(100, 5000),
                    'retries': 0 if success else random.randint(1, 3),
                },
            )
        
        if self.values is not None:
            self.values.observe_outcome(
                action_type=action,
                outcome=outcome,
                context={
                    'duration_ms': random.randint(100, 5000),
                    'retries': 0 if success else random.randint(1, 3),
                    'risk_level': random.choice(['low', 'medium', 'high']),
                    'complexity': random.choice(['low', 'medium', 'high']),
                    'completeness': 'high' if success else 'low',
                    'speed': 'fast' if random.randint(0, 1) else 'slow',
                },
            )
        
        # Track metrics
        self.action_counts[action] = self.action_counts.get(action, 0) + 1
        if success:
            self.success_counts[action] = self.success_counts.get(action, 0) + 1
        
        self.episodes.append({
            'cycle': cycle,
            'action': action,
            'outcome': outcome,
            'success': success,
            'resources': self.resources,
        })
        
        return self.get_metrics()
    
    def get_metrics(self) -> SeedResult:
        """Calculate metrics."""
        total = len(self.episodes)
        if total == 0:
            return SeedResult(
                seed=self.seed,
                success_rate=0,
                action_diversity=0,
                behavioral_consistency=0,
                action_counts={},
                success_counts={},
                identity_coherence=0,
                value_coherence=0,
                stable_preferences=0,
                stable_values=0,
            )
        
        # Success rate
        successes = sum(1 for e in self.episodes if e['success'])
        success_rate = successes / total
        
        # Action diversity (Shannon entropy)
        action_probs = [c / total for c in self.action_counts.values() if c > 0]
        entropy = -sum(p * math.log2(p) for p in action_probs if p > 0)
        max_entropy = math.log2(len(self.action_counts)) if self.action_counts else 1
        diversity = entropy / max_entropy if max_entropy > 0 else 0
        
        # Behavioral consistency
        if total >= 10:
            early = self.episodes[:total // 5]
            late = self.episodes[-total // 5:]
            early_rate = sum(1 for e in early if e['success']) / len(early)
            late_rate = sum(1 for e in late if e['success']) / len(late)
            consistency = 1.0 - abs(early_rate - late_rate)
        else:
            consistency = 0.5
        
        # Developmental metrics
        identity_coherence = self.identity.state.identity_coherence if self.identity else 0
        value_coherence = self.values.state.value_coherence if self.values else 0
        stable_prefs = len(self.identity.get_stable_preferences()) if self.identity else 0
        stable_vals = len(self.values.get_stable_values()) if self.values else 0
        
        return SeedResult(
            seed=self.seed,
            success_rate=success_rate,
            action_diversity=diversity,
            behavioral_consistency=consistency,
            action_counts=self.action_counts.copy(),
            success_counts=self.success_counts.copy(),
            identity_coherence=identity_coherence,
            value_coherence=value_coherence,
            stable_preferences=stable_prefs,
            stable_values=stable_vals,
            catastrophes_survived=self.catastrophes_survived,
            resource_efficiency=self.resources / 100,
        )


def calculate_ci(values: List[float], confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate confidence interval."""
    n = len(values)
    if n < 2:
        return (0, 0)
    
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    
    # t-critical value (approximation for large n)
    # For 95% CI with n > 30, z ≈ 1.96
    z = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645
    
    margin = z * (std / math.sqrt(n))
    return (mean - margin, mean + margin)


def cohens_d(group1: List[float], group2: List[float]) -> float:
    """Calculate Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return 0
    
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1, var2 = statistics.variance(group1), statistics.variance(group2)
    
    # Pooled standard deviation
    pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_std == 0:
        return 0
    
    return (mean1 - mean2) / pooled_std


def welch_t_test(group1: List[float], group2: List[float]) -> Tuple[float, float]:
    """Welch's t-test for unequal variances."""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return (0, 1)
    
    mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
    var1, var2 = statistics.variance(group1), statistics.variance(group2)
    
    # Standard error
    se = math.sqrt(var1/n1 + var2/n2)
    
    if se == 0:
        return (0, 1)
    
    t_stat = (mean1 - mean2) / se
    
    # Approximate p-value using normal distribution for large samples
    # For rigorous analysis, use scipy
    z = abs(t_stat)
    p_value = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    
    return (t_stat, p_value)


def run_experiment_suite(config: ExperimentConfig) -> Dict[str, Any]:
    """Run complete experiment suite."""
    print(f"\n{'='*60}")
    print(f"Running: {config.name}")
    print(f"Seeds: {config.num_seeds}, Episodes: {config.episodes_per_seed}")
    print(f"{'='*60}")
    
    results = []
    for seed in range(config.num_seeds):
        if (seed + 1) % 20 == 0:
            print(f"  Seed {seed + 1}/{config.num_seeds}...")
        
        agent = AgentSimulator(config, seed)
        
        for episode in range(config.episodes_per_seed):
            agent.simulate_episode(episode)
        
        result = agent.get_metrics()
        results.append(result)
    
    return analyze_results(config.name, results)


def analyze_results(name: str, results: List[SeedResult]) -> Dict[str, Any]:
    """Analyze results with statistical rigor."""
    
    success_rates = [r.success_rate for r in results]
    diversities = [r.action_diversity for r in results]
    consistencies = [r.behavioral_consistency for r in results]
    identity_coherences = [r.identity_coherence for r in results]
    value_coherences = [r.value_coherence for r in results]
    
    return {
        'name': name,
        'n': len(results),
        'success_rate': {
            'mean': statistics.mean(success_rates),
            'std': statistics.stdev(success_rates) if len(success_rates) > 1 else 0,
            'median': statistics.median(success_rates),
            'ci_95': calculate_ci(success_rates),
            'min': min(success_rates),
            'max': max(success_rates),
        },
        'action_diversity': {
            'mean': statistics.mean(diversities),
            'std': statistics.stdev(diversities) if len(diversities) > 1 else 0,
            'ci_95': calculate_ci(diversities),
        },
        'behavioral_consistency': {
            'mean': statistics.mean(consistencies),
            'std': statistics.stdev(consistencies) if len(consistencies) > 1 else 0,
            'ci_95': calculate_ci(consistencies),
        },
        'identity_coherence': {
            'mean': statistics.mean(identity_coherences),
            'std': statistics.stdev(identity_coherences) if len(identity_coherences) > 1 else 0,
        },
        'value_coherence': {
            'mean': statistics.mean(value_coherences),
            'std': statistics.stdev(value_coherences) if len(value_coherences) > 1 else 0,
        },
        'raw_results': [
            {
                'seed': r.seed,
                'success_rate': r.success_rate,
                'diversity': r.action_diversity,
                'consistency': r.behavioral_consistency,
                'identity_coherence': r.identity_coherence,
                'value_coherence': r.value_coherence,
            }
            for r in results
        ],
    }


def main():
    num_seeds = 120
    episodes = 100
    
    print("="*60)
    print("RIGOROUS DEVELOPMENTAL COGNITION EXPERIMENT")
    print("="*60)
    print(f"Seeds: {num_seeds}, Episodes per seed: {episodes}")
    print(f"Total episodes: {num_seeds * episodes}")
    
    # Define experiment configurations
    experiments = [
        # Baseline
        ExperimentConfig(
            name="Static (Baseline)",
            use_memory_influence=False,
            use_identity=False,
            use_values=False,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
        ),
        # Full developmental system
        ExperimentConfig(
            name="Developmental (Full)",
            use_memory_influence=True,
            use_identity=True,
            use_values=True,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
        ),
        # Ablation: Memory only
        ExperimentConfig(
            name="Memory Only",
            use_memory_influence=True,
            use_identity=False,
            use_values=False,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
        ),
        # Ablation: Identity only
        ExperimentConfig(
            name="Identity Only",
            use_memory_influence=False,
            use_identity=True,
            use_values=False,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
        ),
        # Ablation: Values only
        ExperimentConfig(
            name="Values Only",
            use_memory_influence=False,
            use_identity=False,
            use_values=True,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
        ),
        # Stress test: Catastrophic events
        ExperimentConfig(
            name="Catastrophic Events",
            use_memory_influence=True,
            use_identity=True,
            use_values=True,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
            catastrophic_event_prob=0.1,
        ),
        # Stress test: Resource scarcity
        ExperimentConfig(
            name="Resource Scarcity",
            use_memory_influence=True,
            use_identity=True,
            use_values=True,
            num_seeds=num_seeds,
            episodes_per_seed=episodes,
            resource_scarcity=0.5,
        ),
    ]
    
    # Run all experiments
    all_results = []
    for config in experiments:
        result = run_experiment_suite(config)
        all_results.append(result)
    
    # Statistical comparisons
    print("\n" + "="*60)
    print("STATISTICAL ANALYSIS")
    print("="*60)
    
    baseline = all_results[0]
    developmental = all_results[1]
    
    # Extract raw success rates for comparison
    baseline_rates = [r['success_rate'] for r in baseline['raw_results']]
    dev_rates = [r['success_rate'] for r in developmental['raw_results']]
    
    t_stat, p_value = welch_t_test(dev_rates, baseline_rates)
    effect_size = cohens_d(dev_rates, baseline_rates)
    
    print(f"\nDevelopmental vs Baseline:")
    print(f"  Baseline success rate: {baseline['success_rate']['mean']:.3f} ± {baseline['success_rate']['std']:.3f}")
    print(f"  Developmental success rate: {developmental['success_rate']['mean']:.3f} ± {developmental['success_rate']['std']:.3f}")
    print(f"  Difference: {developmental['success_rate']['mean'] - baseline['success_rate']['mean']:.3f}")
    print(f"  t-statistic: {t_stat:.3f}")
    print(f"  p-value: {p_value:.6f}")
    print(f"  Cohen's d: {effect_size:.3f}")
    print(f"  Significant (p < 0.05): {'Yes' if p_value < 0.05 else 'No'}")
    
    # Effect size interpretation
    if abs(effect_size) < 0.2:
        effect_interp = "negligible"
    elif abs(effect_size) < 0.5:
        effect_interp = "small"
    elif abs(effect_size) < 0.8:
        effect_interp = "medium"
    else:
        effect_interp = "large"
    print(f"  Effect size: {effect_interp}")
    
    # Ablation analysis
    print("\n" + "="*60)
    print("ABLATION ANALYSIS")
    print("="*60)
    
    ablation_names = ["Memory Only", "Identity Only", "Values Only"]
    ablation_results = all_results[2:5]
    
    for name, result in zip(ablation_names, ablation_results):
        ablation_rates = [r['success_rate'] for r in result['raw_results']]
        t, p = welch_t_test(ablation_rates, baseline_rates)
        d = cohens_d(ablation_rates, baseline_rates)
        
        print(f"\n{name} vs Baseline:")
        print(f"  Success rate: {result['success_rate']['mean']:.3f} ± {result['success_rate']['std']:.3f}")
        print(f"  Improvement: {(result['success_rate']['mean'] - baseline['success_rate']['mean']) / baseline['success_rate']['mean'] * 100:.1f}%")
        print(f"  Cohen's d: {d:.3f}")
        print(f"  p-value: {p:.6f}")
    
    # Stress test analysis
    print("\n" + "="*60)
    print("STRESS TEST ANALYSIS")
    print("="*60)
    
    stress_names = ["Catastrophic Events", "Resource Scarcity"]
    stress_results = all_results[5:7]
    
    for name, result in zip(stress_names, stress_results):
        stress_rates = [r['success_rate'] for r in result['raw_results']]
        t, p = welch_t_test(stress_rates, dev_rates)
        d = cohens_d(stress_rates, dev_rates)
        
        print(f"\n{name} vs Full Developmental:")
        print(f"  Success rate: {result['success_rate']['mean']:.3f} ± {result['success_rate']['std']:.3f}")
        print(f"  Degradation: {(result['success_rate']['mean'] - developmental['success_rate']['mean']) / developmental['success_rate']['mean'] * 100:.1f}%")
        print(f"  Resilience: {100 + (result['success_rate']['mean'] - developmental['success_rate']['mean']) / developmental['success_rate']['mean'] * 100:.1f}%")
    
    # Save results
    output = {
        'parameters': {
            'num_seeds': num_seeds,
            'episodes_per_seed': episodes,
        },
        'experiments': all_results,
        'statistical_tests': {
            'developmental_vs_baseline': {
                't_statistic': t_stat,
                'p_value': p_value,
                'cohens_d': effect_size,
                'effect_size': effect_interp,
            },
        },
    }
    
    output_path = Path("rigorous_experiment_results.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    
    # Generate plots
    generate_plots(all_results)


def generate_plots(results: List[Dict[str, Any]]):
    """Generate publication-quality plots."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available, skipping plots")
        return
    
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('Developmental Cognition Experiment Results', fontsize=14, fontweight='bold')
    
    # Plot 1: Success rates with confidence intervals
    ax = axes[0, 0]
    names = [r['name'] for r in results]
    means = [r['success_rate']['mean'] for r in results]
    ci_lows = [r['success_rate']['ci_95'][0] for r in results]
    ci_highs = [r['success_rate']['ci_95'][1] for r in results]
    errors = [[m - l for m, l in zip(means, ci_lows)],
              [h - m for m, h in zip(means, ci_highs)]]
    
    x = np.arange(len(names))
    ax.bar(x, means, yerr=errors, capsize=5, color=['gray', 'green', 'blue', 'orange', 'red', 'purple', 'brown'])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Success Rate')
    ax.set_title('Success Rate with 95% CI')
    ax.set_ylim(0, 1)
    
    # Plot 2: Distributions
    ax = axes[0, 1]
    for i, result in enumerate(results[:4]):  # First 4 experiments
        rates = [r['success_rate'] for r in result['raw_results']]
        ax.hist(rates, bins=20, alpha=0.5, label=result['name'], density=True)
    ax.set_xlabel('Success Rate')
    ax.set_ylabel('Density')
    ax.set_title('Success Rate Distributions')
    ax.legend(fontsize=8)
    
    # Plot 3: Effect sizes
    ax = axes[0, 2]
    baseline_rates = [r['success_rate'] for r in results[0]['raw_results']]
    effect_sizes = []
    for result in results[1:]:
        rates = [r['success_rate'] for r in result['raw_results']]
        d = cohens_d(rates, baseline_rates)
        effect_sizes.append(d)
    
    colors = ['green' if d > 0 else 'red' for d in effect_sizes]
    ax.barh(range(len(effect_sizes)), effect_sizes, color=colors)
    ax.set_yticks(range(len(effect_sizes)))
    ax.set_yticklabels([r['name'] for r in results[1:]], fontsize=8)
    ax.set_xlabel("Cohen's d")
    ax.set_title('Effect Sizes vs Baseline')
    ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax.axvline(x=0.2, color='gray', linestyle='--', linewidth=0.5, label='Small')
    ax.axvline(x=0.5, color='gray', linestyle='--', linewidth=0.5, label='Medium')
    ax.axvline(x=0.8, color='gray', linestyle='--', linewidth=0.5, label='Large')
    
    # Plot 4: Identity coherence over experiments
    ax = axes[1, 0]
    identity_means = [r['identity_coherence']['mean'] for r in results]
    ax.bar(x, identity_means, color=['gray', 'green', 'blue', 'orange', 'red', 'purple', 'brown'])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Identity Coherence')
    ax.set_title('Identity Coherence by Experiment')
    ax.set_ylim(0, 1)
    
    # Plot 5: Value coherence over experiments
    ax = axes[1, 1]
    value_means = [r['value_coherence']['mean'] for r in results]
    ax.bar(x, value_means, color=['gray', 'green', 'blue', 'orange', 'red', 'purple', 'brown'])
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Value Coherence')
    ax.set_title('Value Coherence by Experiment')
    ax.set_ylim(0, 1)
    
    # Plot 6: Resilience under stress
    ax = axes[1, 2]
    stress_names = ['Baseline', 'Catastrophic', 'Scarcity']
    stress_means = [results[0]['success_rate']['mean'], 
                    results[5]['success_rate']['mean'],
                    results[6]['success_rate']['mean']]
    resilience = [s / results[0]['success_rate']['mean'] * 100 for s in stress_means]
    
    ax.bar(stress_names, resilience, color=['gray', 'red', 'orange'])
    ax.set_ylabel('Resilience (% of baseline)')
    ax.set_title('Stress Test Resilience')
    ax.axhline(y=100, color='black', linestyle='--', linewidth=0.5)
    
    plt.tight_layout()
    
    plot_path = Path("experiment_results.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Plots saved to {plot_path}")
    plt.close()


if __name__ == "__main__":
    main()
