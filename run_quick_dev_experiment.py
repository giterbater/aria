#!/usr/bin/env python3
"""
Quick Developmental Cognition Experiment

Validates that memory influence, identity formation, and value formation
work together in a controlled setting.
"""

import random
import json
from pathlib import Path

from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.memory.influence import MemoryInfluenceEngine
from aria_core.identity.formation import IdentityFormationEngine
from aria_core.values.formation import ValueFormationEngine
from aria_core.memory.models import EpisodicItem, Outcome


def run_experiment(seed: int = 42, cycles: int = 50) -> dict:
    """Run a focused developmental experiment."""
    random.seed(seed)
    
    # Initialize engines
    memory = SimpleMemorySystem()
    influence = MemoryInfluenceEngine(memory, min_episodes_for_pattern=3)
    identity = IdentityFormationEngine(min_episodes_for_preference=3)
    values = ValueFormationEngine(min_signals_for_value=3)
    
    # Track results
    results = []
    snapshots = []
    
    action_types = ['inform', 'execute', 'query', 'warn']
    
    for cycle in range(cycles):
        # Simulate action selection (biased by current state)
        action = random.choice(action_types)
        
        # Simulate outcome (with some patterns)
        # 'inform' tends to succeed, 'warn' tends to fail
        if action == 'inform':
            success_prob = 0.8
        elif action == 'warn':
            success_prob = 0.3
        elif action == 'execute':
            success_prob = 0.6
        else:  # query
            success_prob = 0.7
        
        success = random.random() < success_prob
        outcome = 'success' if success else 'failed'
        
        # Record in memory
        episode = EpisodicItem(
            importance=0.6 if success else 0.4,
            structured_input={"text": f"action {cycle}"},
            decision=type('Decision', (), {'action_type': action, 'payload': {}})(),
            outcome=Outcome.SUCCESS.value if success else Outcome.FAILED.value,
        )
        memory.store_episodic(episode)
        
        # Record for identity formation
        identity.observe_action(
            action_type=action,
            outcome=outcome,
            context={
                'risk_level': random.choice(['low', 'medium', 'high']),
                'duration_ms': random.randint(100, 5000),
                'retries': 0 if success else random.randint(1, 3),
            },
        )
        
        # Record for value formation
        values.observe_outcome(
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
        
        # Compute influence signals
        influence_signals = influence.compute_influences(limit=5)
        
        # Take snapshot
        snapshot = {
            'cycle': cycle + 1,
            'action': action,
            'outcome': outcome,
            'identity_coherence': identity.state.identity_coherence,
            'value_coherence': values.state.value_coherence,
            'total_experiences': identity.state.total_experiences,
            'total_value_signals': values.state.total_signals,
            'stable_preferences': len(identity.get_stable_preferences()),
            'stable_values': len(values.get_stable_values()),
            'influence_signals': len(influence_signals),
        }
        snapshots.append(snapshot)
        
        results.append({
            'cycle': cycle + 1,
            'action': action,
            'outcome': outcome,
        })
    
    # Final analysis
    success_rate = sum(1 for r in results if r['outcome'] == 'success') / len(results)
    
    # Analyze action distribution
    action_counts = {}
    for r in results:
        action_counts[r['action']] = action_counts.get(r['action'], 0) + 1
    
    # Analyze influence signals
    final_influence = influence.get_influence_summary()
    final_identity = identity.get_identity_summary()
    final_values = values.get_value_summary()
    
    experiment_result = {
        'seed': seed,
        'cycles': cycles,
        'success_rate': success_rate,
        'action_distribution': action_counts,
        'final_influence': final_influence,
        'final_identity': final_identity,
        'final_values': final_values,
        'snapshots': snapshots,
    }
    
    return experiment_result


def main():
    print("Running developmental cognition experiment...")
    
    # Run experiment
    result = run_experiment(seed=42, cycles=50)
    
    # Print summary
    print(f"\n=== Experiment Results ===")
    print(f"Seed: {result['seed']}")
    print(f"Cycles: {result['cycles']}")
    print(f"Success Rate: {result['success_rate']:.2%}")
    print(f"\nAction Distribution:")
    for action, count in result['action_distribution'].items():
        print(f"  {action}: {count}")
    
    print(f"\n=== Influence Summary ===")
    print(result['final_influence'])
    
    print(f"\n=== Identity Summary ===")
    print(result['final_identity'])
    
    print(f"\n=== Values Summary ===")
    print(result['final_values'])
    
    # Save results
    output_path = Path("developmental_experiment_result.json")
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    
    # Check for emergent behaviors
    print(f"\n=== Emergent Behaviors ===")
    
    # Check if influence signals emerged
    influence_data = result['final_influence']
    if influence_data.get('signal_count', 0) > 0:
        print(f"✓ Memory influence signals emerged: {influence_data['signal_count']}")
        for pref in influence_data.get('top_preferences', []):
            print(f"  - {pref['action']}: strength={pref['strength']:.2f} ({pref['reason']})")
    else:
        print("✗ No memory influence signals emerged")
    
    # Check if identity formed (use snapshots since summary returns string)
    last_snapshot = result['snapshots'][-1] if result['snapshots'] else {}
    stable_prefs = last_snapshot.get('stable_preferences', 0)
    if stable_prefs > 0:
        print(f"✓ Identity formed: {stable_prefs} stable preferences")
    else:
        print("✗ Identity not yet stable")
    
    # Check if values formed (use snapshots since summary returns string)
    stable_vals = last_snapshot.get('stable_values', 0)
    if stable_vals > 0:
        print(f"✓ Values formed: {stable_vals} stable values")
    else:
        print("✗ Values not yet stable")


if __name__ == "__main__":
    main()
