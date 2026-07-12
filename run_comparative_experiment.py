#!/usr/bin/env python3
"""
Comparative Experiment: Static vs Developmental Agents

Hypothesis: Developmental cognition improves long-term adaptation.

Method:
- Run N seeds with static agents (no memory influence, no identity, no values)
- Run N seeds with developmental agents (full system)
- Compare: survival, planning quality, innovation, cooperation, benchmark score

Metrics:
- Success rate
- Action diversity
- Identity coherence
- Value coherence
- Behavioral consistency
"""

import random
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Callable

from aria_core.memory.simple_memory_system import SimpleMemorySystem
from aria_core.memory.influence import MemoryInfluenceEngine
from aria_core.identity.formation import IdentityFormationEngine
from aria_core.values.formation import ValueFormationEngine
from aria_core.memory.models import EpisodicItem, Outcome


class AgentSimulator:
    """Simulates an agent making decisions based on its configuration."""
    
    def __init__(
        self,
        name: str,
        use_memory_influence: bool = False,
        use_identity: bool = False,
        use_values: bool = False,
        seed: int = 42,
    ):
        self.name = name
        self.seed = seed
        self.use_memory_influence = use_memory_influence
        self.use_identity = use_identity
        self.use_values = use_values
        
        random.seed(seed)
        
        # Initialize systems
        self.memory = SimpleMemorySystem()
        self.influence = MemoryInfluenceEngine(self.memory) if use_memory_influence else None
        self.identity = IdentityFormationEngine() if use_identity else None
        self.values = ValueFormationEngine() if use_values else None
        
        # Track metrics
        self.episodes: List[Dict[str, Any]] = []
        self.action_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
    
    def decide(self, context: Dict[str, Any]) -> str:
        """Make a decision based on current state."""
        action_types = ['inform', 'execute', 'query', 'warn']
        
        # Base probabilities
        probs = {a: 0.25 for a in action_types}
        
        # Apply memory influence if enabled
        if self.influence is not None:
            signals = self.influence.compute_influences(limit=10)
            for signal in signals:
                if signal.action_preference in probs:
                    # Adjust probability based on signal strength
                    adjustment = signal.strength * 0.3
                    probs[signal.action_preference] += adjustment
            
            # Normalize probabilities
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Apply identity preferences if enabled
        if self.identity is not None:
            identity_signals = self.identity.get_identity_signals()
            action_prefs = identity_signals.get('action_preferences', {})
            for action, strength in action_prefs.items():
                if action in probs:
                    probs[action] += strength * 0.2
            
            # Normalize
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Apply value preferences if enabled
        if self.values is not None:
            value_signals = self.values.get_value_signals()
            active_values = value_signals.get('active_values', {})
            # Values can influence which actions are preferred
            for value_name, value_data in active_values.items():
                if value_data.get('direction') == 'positive':
                    # Strong values can slightly boost related actions
                    if value_name == 'efficiency' and 'execute' in probs:
                        probs['execute'] += 0.1
                    elif value_name == 'curiosity' and 'query' in probs:
                        probs['query'] += 0.1
            
            # Normalize
            total = sum(probs.values())
            probs = {a: p / total for a, p in probs.items()}
        
        # Select action based on probabilities
        actions = list(probs.keys())
        weights = list(probs.values())
        
        return random.choices(actions, weights=weights, k=1)[0]
    
    def simulate_episode(self, cycle: int) -> Dict[str, Any]:
        """Simulate one episode of decision-making."""
        # Make decision
        context = {'cycle': cycle}
        action = self.decide(context)
        
        # Determine outcome (fixed probabilities for comparability)
        success_probs = {'inform': 0.8, 'execute': 0.6, 'query': 0.7, 'warn': 0.3}
        success = random.random() < success_probs[action]
        outcome = 'success' if success else 'failed'
        
        # Record in memory
        episode = EpisodicItem(
            importance=0.6 if success else 0.4,
            structured_input={"text": f"action {cycle}"},
            decision=type('Decision', (), {'action_type': action, 'payload': {}})(),
            outcome=Outcome.SUCCESS.value if success else Outcome.FAILED.value,
        )
        self.memory.store_episodic(episode)
        
        # Update influence if enabled
        if self.influence is not None:
            # Influence is computed on-demand from memory
            pass
        
        # Update identity if enabled
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
        
        # Update values if enabled
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
        
        # Record episode
        episode_data = {
            'cycle': cycle,
            'action': action,
            'outcome': outcome,
            'success': success,
        }
        self.episodes.append(episode_data)
        
        return episode_data
    
    def get_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive metrics."""
        total_episodes = len(self.episodes)
        if total_episodes == 0:
            return {}
        
        # Success rate
        total_successes = sum(1 for e in self.episodes if e['success'])
        success_rate = total_successes / total_episodes
        
        # Action diversity (Shannon entropy)
        import math
        action_probs = []
        for count in self.action_counts.values():
            prob = count / total_episodes
            if prob > 0:
                action_probs.append(prob)
        
        entropy = -sum(p * math.log2(p) for p in action_probs)
        max_entropy = math.log2(len(self.action_counts)) if self.action_counts else 1
        diversity = entropy / max_entropy if max_entropy > 0 else 0
        
        # Success rate by action
        action_success_rates = {}
        for action in self.action_counts:
            if action in self.success_counts:
                action_success_rates[action] = self.success_counts[action] / self.action_counts[action]
            else:
                action_success_rates[action] = 0.0
        
        # Behavioral consistency (last 20% vs first 20%)
        if total_episodes >= 10:
            early = self.episodes[:total_episodes // 5]
            late = self.episodes[-total_episodes // 5:]
            
            early_rate = sum(1 for e in early if e['success']) / len(early)
            late_rate = sum(1 for e in late if e['success']) / len(late)
            
            consistency = 1.0 - abs(early_rate - late_rate)
        else:
            consistency = 0.5
        
        # Developmental metrics
        identity_coherence = 0.0
        value_coherence = 0.0
        stable_preferences = 0
        stable_values = 0
        
        if self.identity is not None:
            identity_coherence = self.identity.state.identity_coherence
            stable_preferences = len(self.identity.get_stable_preferences())
        
        if self.values is not None:
            value_coherence = self.values.state.value_coherence
            stable_values = len(self.values.get_stable_values())
        
        return {
            'total_episodes': total_episodes,
            'success_rate': success_rate,
            'action_diversity': diversity,
            'action_success_rates': action_success_rates,
            'behavioral_consistency': consistency,
            'identity_coherence': identity_coherence,
            'value_coherence': value_coherence,
            'stable_preferences': stable_preferences,
            'stable_values': stable_values,
        }


def run_comparative_experiment(
    num_seeds: int = 10,
    episodes_per_seed: int = 100,
) -> Dict[str, Any]:
    """Run comparative experiment between static and developmental agents."""
    
    print(f"Running comparative experiment...")
    print(f"Seeds: {num_seeds}, Episodes per seed: {episodes_per_seed}")
    
    static_results = []
    developmental_results = []
    
    for seed in range(num_seeds):
        print(f"  Seed {seed + 1}/{num_seeds}...")
        
        # Static agent (no developmental components)
        static_agent = AgentSimulator(
            name="static",
            use_memory_influence=False,
            use_identity=False,
            use_values=False,
            seed=seed,
        )
        
        # Developmental agent (full system)
        dev_agent = AgentSimulator(
            name="developmental",
            use_memory_influence=True,
            use_identity=True,
            use_values=True,
            seed=seed,
        )
        
        # Run episodes
        for episode in range(episodes_per_seed):
            static_agent.simulate_episode(episode)
            dev_agent.simulate_episode(episode)
        
        # Collect metrics
        static_metrics = static_agent.get_metrics()
        dev_metrics = dev_agent.get_metrics()
        
        static_results.append(static_metrics)
        developmental_results.append(dev_metrics)
    
    # Aggregate results
    def aggregate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results:
            return {}
        
        metrics = {}
        for key in results[0]:
            if isinstance(results[0][key], (int, float)):
                values = [r[key] for r in results]
                metrics[key] = {
                    'mean': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'std': (sum((v - sum(values)/len(values))**2 for v in values) / len(values)) ** 0.5,
                }
            elif isinstance(results[0][key], dict):
                # Aggregate dictionaries
                aggregated = {}
                for r in results:
                    for k, v in r[key].items():
                        if k not in aggregated:
                            aggregated[k] = []
                        aggregated[k].append(v)
                metrics[key] = {
                    k: sum(v) / len(v) for k, v in aggregated.items()
                }
        
        return metrics
    
    static_aggregated = aggregate_metrics(static_results)
    dev_aggregated = aggregate_metrics(developmental_results)
    
    # Statistical comparison
    comparison = {}
    for key in ['success_rate', 'action_diversity', 'behavioral_consistency']:
        if key in static_aggregated and key in dev_aggregated:
            static_val = static_aggregated[key]['mean']
            dev_val = dev_aggregated[key]['mean']
            
            if static_val > 0:
                improvement = (dev_val - static_val) / static_val * 100
            else:
                improvement = 0
            
            comparison[key] = {
                'static_mean': static_val,
                'developmental_mean': dev_val,
                'improvement_pct': improvement,
            }
    
    return {
        'parameters': {
            'num_seeds': num_seeds,
            'episodes_per_seed': episodes_per_seed,
        },
        'static_results': static_results,
        'developmental_results': developmental_results,
        'static_aggregated': static_aggregated,
        'developmental_aggregated': dev_aggregated,
        'comparison': comparison,
    }


def main():
    # Run experiment
    results = run_comparative_experiment(num_seeds=10, episodes_per_seed=100)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"COMPARATIVE EXPERIMENT RESULTS")
    print(f"{'='*60}")
    
    print(f"\nStatic Agent Metrics:")
    for key, value in results['static_aggregated'].items():
        if isinstance(value, dict) and 'mean' in value:
            print(f"  {key}: {value['mean']:.3f} (±{value['std']:.3f})")
    
    print(f"\nDevelopmental Agent Metrics:")
    for key, value in results['developmental_aggregated'].items():
        if isinstance(value, dict) and 'mean' in value:
            print(f"  {key}: {value['mean']:.3f} (±{value['std']:.3f})")
    
    print(f"\nComparison:")
    for key, value in results['comparison'].items():
        improvement = value['improvement_pct']
        direction = "better" if improvement > 0 else "worse"
        print(f"  {key}: {abs(improvement):.1f}% {direction}")
    
    # Check hypothesis
    print(f"\n{'='*60}")
    print(f"HYPOTHESIS VALIDATION")
    print(f"{'='*60}")
    
    hypothesis_supported = True
    
    # Check success rate
    if results['comparison']['success_rate']['improvement_pct'] < 0:
        print(f"✗ Success rate: Developmental agent performed worse")
        hypothesis_supported = False
    else:
        print(f"✓ Success rate: Developmental agent performed better or equal")
    
    # Check action diversity
    if results['comparison']['action_diversity']['improvement_pct'] < 0:
        print(f"✗ Action diversity: Developmental agent less diverse")
        hypothesis_supported = False
    else:
        print(f"✓ Action diversity: Developmental agent more diverse or equal")
    
    # Check behavioral consistency
    if results['comparison']['behavioral_consistency']['improvement_pct'] < 0:
        print(f"✗ Behavioral consistency: Developmental agent less consistent")
        hypothesis_supported = False
    else:
        print(f"✓ Behavioral consistency: Developmental agent more consistent or equal")
    
    if hypothesis_supported:
        print(f"\n✓ HYPOTHESIS SUPPORTED: Developmental cognition improves adaptation")
    else:
        print(f"\n✗ HYPOTHESIS NOT FULLY SUPPORTED: Mixed results")
    
    # Save results
    output_path = Path("comparative_experiment_results.json")
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
