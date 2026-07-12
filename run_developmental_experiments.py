#!/usr/bin/env python3
"""
Developmental Cognition Experiments

Research questions:
1. Does memory influence create behavioral biases?
2. Does identity emerge from repeated experiences?
3. Do values form from outcome patterns?
4. How do these components interact?
5. What are the failure modes?

Usage:
    python run_developmental_experiments.py
    python run_developmental_experiments.py --seeds 10 --objectives 20
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import List, Dict, Any

from aria_core.integration import ARIACore
from aria_core.memory.influence import MemoryInfluenceEngine
from aria_core.identity.formation import IdentityFormationEngine, IdentityDimension
from aria_core.values.formation import ValueFormationEngine, ValueType


def run_experiment(
    seed: int,
    num_objectives: int,
    objective_templates: List[str],
) -> Dict[str, Any]:
    """Run a single experiment with given parameters."""
    random.seed(seed)
    
    core = ARIACore(llm=None, db_path=":memory:")
    
    results = []
    snapshots = []
    
    for i in range(num_objectives):
        # Select objective template
        template = objective_templates[i % len(objective_templates)]
        objective = f"{template} {i}"
        
        # Process objective
        t0 = time.time()
        result = core.process_objective(objective)
        elapsed = time.time() - t0
        
        result['elapsed'] = elapsed
        results.append(result)
        
        # Take snapshot of developmental state
        snapshot = {
            'cycle': i + 1,
            'success': result['success'],
            'identity_coherence': core.identity.state.identity_coherence,
            'value_coherence': core.values.state.value_coherence,
            'total_experiences': core.identity.state.total_experiences,
            'total_value_signals': core.values.state.total_signals,
            'stable_preferences': len(core.identity.get_stable_preferences()),
            'stable_values': len(core.values.get_stable_values()),
            'memory_influence_signals': len(core.memory_influence._influence_cache),
        }
        snapshots.append(snapshot)
    
    # Final state
    final_status = core.get_status()
    
    # Analysis
    success_rate = sum(r['success'] for r in results) / len(results)
    avg_duration = sum(r['duration_ms'] for r in results) / len(results)
    
    experiment_result = {
        'seed': seed,
        'num_objectives': num_objectives,
        'success_rate': success_rate,
        'avg_duration_ms': avg_duration,
        'final_status': final_status,
        'snapshots': snapshots,
        'results': results,
    }
    
    core.shutdown()
    return experiment_result


def analyze_results(experiments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze results across multiple experiments."""
    analysis = {
        'num_experiments': len(experiments),
        'seeds': [e['seed'] for e in experiments],
    }
    
    # Aggregate success rates
    success_rates = [e['success_rate'] for e in experiments]
    analysis['avg_success_rate'] = sum(success_rates) / len(success_rates)
    analysis['min_success_rate'] = min(success_rates)
    analysis['max_success_rate'] = max(success_rates)
    analysis['success_rate_std'] = (sum((r - analysis['avg_success_rate']) ** 2 for r in success_rates) / len(success_rates)) ** 0.5
    
    # Aggregate durations
    durations = [e['avg_duration_ms'] for e in experiments]
    analysis['avg_duration_ms'] = sum(durations) / len(durations)
    
    # Developmental state analysis
    final_identities = [e['final_status']['developmental']['identity'] for e in experiments]
    final_values = [e['final_status']['developmental']['values'] for e in experiments]
    
    analysis['identity_coherence'] = {
        'mean': sum(i['coherence'] for i in final_identities) / len(final_identities),
        'min': min(i['coherence'] for i in final_identities),
        'max': max(i['coherence'] for i in final_identities),
    }
    
    analysis['value_coherence'] = {
        'mean': sum(v['coherence'] for v in final_values) / len(final_values),
        'min': min(v['coherence'] for v in final_values),
        'max': max(v['coherence'] for v in final_values),
    }
    
    # Behavioral consistency
    consistency_scores = []
    for exp in experiments:
        snapshots = exp['snapshots']
        if len(snapshots) > 2:
            # Check if success rate stabilizes
            early = [s['success'] for s in snapshots[:len(snapshots)//2]]
            late = [s['success'] for s in snapshots[len(snapshots)//2:]]
            
            early_rate = sum(early) / len(early) if early else 0
            late_rate = sum(late) / len(late) if late else 0
            
            consistency = 1.0 - abs(early_rate - late_rate)
            consistency_scores.append(consistency)
    
    if consistency_scores:
        analysis['behavioral_consistency'] = {
            'mean': sum(consistency_scores) / len(consistency_scores),
            'min': min(consistency_scores),
            'max': max(consistency_scores),
        }
    
    return analysis


def run_ablation_study(
    num_seeds: int = 5,
    num_objectives: int = 15,
) -> Dict[str, Any]:
    """Run ablation study comparing with and without developmental components."""
    results = {
        'with_developmental': [],
        'without_memory_influence': [],
        'without_identity': [],
        'without_values': [],
    }
    
    objective_templates = [
        "read and analyze",
        "test and fix",
        "create and build",
        "review and improve",
    ]
    
    for seed in range(num_seeds):
        # Full developmental system
        exp = run_experiment(seed, num_objectives, objective_templates)
        results['with_developmental'].append(exp)
        
        # Without memory influence
        core = ARIACore(llm=None, db_path=":memory:")
        core.memory_influence._influence_weight = 0.0
        exp_no_memory = run_ablation_variant(core, seed, num_objectives, objective_templates)
        results['without_memory_influence'].append(exp_no_memory)
        
        # Without identity
        core = ARIACore(llm=None, db_path=":memory:")
        original_observe = core.identity.observe_action
        core.identity.observe_action = lambda *args, **kwargs: None
        exp_no_identity = run_ablation_variant(core, seed, num_objectives, objective_templates)
        results['without_identity'].append(exp_no_identity)
        
        # Without values
        core = ARIACore(llm=None, db_path=":memory:")
        original_observe = core.values.observe_outcome
        core.values.observe_outcome = lambda *args, **kwargs: None
        exp_no_values = run_ablation_variant(core, seed, num_objectives, objective_templates)
        results['without_values'].append(exp_no_values)
    
    return results


def run_ablation_variant(
    core: ARIACore,
    seed: int,
    num_objectives: int,
    objective_templates: List[str],
) -> Dict[str, Any]:
    """Run experiment with a specific core configuration."""
    random.seed(seed)
    
    results = []
    snapshots = []
    
    for i in range(num_objectives):
        template = objective_templates[i % len(objective_templates)]
        objective = f"{template} {i}"
        
        result = core.process_objective(objective)
        results.append(result)
        
        snapshot = {
            'cycle': i + 1,
            'success': result['success'],
            'identity_coherence': core.identity.state.identity_coherence,
            'value_coherence': core.values.state.value_coherence,
        }
        snapshots.append(snapshot)
    
    final_status = core.get_status()
    success_rate = sum(r['success'] for r in results) / len(results)
    
    experiment_result = {
        'seed': seed,
        'num_objectives': num_objectives,
        'success_rate': success_rate,
        'final_status': final_status,
        'snapshots': snapshots,
    }
    
    core.shutdown()
    return experiment_result


def main():
    parser = argparse.ArgumentParser(description="Run developmental cognition experiments")
    parser.add_argument("--seeds", type=int, default=5, help="Number of random seeds")
    parser.add_argument("--objectives", type=int, default=15, help="Number of objectives per experiment")
    parser.add_argument("--ablation", action="store_true", help="Run ablation study")
    parser.add_argument("--output", default="developmental_experiment_results.json", help="Output file")
    args = parser.parse_args()
    
    print(f"Running developmental cognition experiments...")
    print(f"Seeds: {args.seeds}, Objectives: {args.objectives}")
    
    objective_templates = [
        "read and analyze code structure",
        "test and fix bugs",
        "create new feature",
        "review and improve quality",
        "document architecture",
        "refactor for clarity",
        "optimize performance",
        "integrate components",
    ]
    
    # Run main experiments
    experiments = []
    for seed in range(args.seeds):
        print(f"Running experiment {seed + 1}/{args.seeds}...")
        exp = run_experiment(seed, args.objectives, objective_templates)
        experiments.append(exp)
    
    # Analyze results
    analysis = analyze_results(experiments)
    
    # Run ablation study if requested
    ablation_results = None
    if args.ablation:
        print("Running ablation study...")
        ablation_results = run_ablation_study(args.seeds, args.objectives)
    
    # Compile output
    output = {
        'experiments': experiments,
        'analysis': analysis,
        'ablation': ablation_results,
    }
    
    # Save results
    output_path = Path(args.output)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    print(f"\n=== Analysis Summary ===")
    print(f"Experiments: {analysis['num_experiments']}")
    print(f"Avg Success Rate: {analysis['avg_success_rate']:.2%}")
    print(f"Success Rate Std: {analysis['success_rate_std']:.2%}")
    print(f"Avg Duration: {analysis['avg_duration_ms']:.1f}ms")
    print(f"Identity Coherence: {analysis['identity_coherence']['mean']:.2%}")
    print(f"Value Coherence: {analysis['value_coherence']['mean']:.2%}")
    
    if 'behavioral_consistency' in analysis:
        print(f"Behavioral Consistency: {analysis['behavioral_consistency']['mean']:.2%}")
    
    if ablation_results:
        print(f"\n=== Ablation Study ===")
        for variant, results in ablation_results.items():
            rates = [r['success_rate'] for r in results]
            avg_rate = sum(rates) / len(rates)
            print(f"{variant}: {avg_rate:.2%} success rate")


if __name__ == "__main__":
    main()
