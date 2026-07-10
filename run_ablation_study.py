#!/usr/bin/env python3
"""
Ablation Study — proves what each component contributes.

Uses a multi-armed bandit problem to directly measure learning.
"""

import random
import statistics
import json
import math
from pathlib import Path
from typing import List, Dict, Any

from aria_core.vnext.models import Experience, ExperienceType, EmotionType
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory, MemoryEntry, MemoryType


class BanditEnvironment:
    """Multi-armed bandit problem."""
    
    def __init__(self, seed: int = 42, num_arms: int = 5):
        self._rng = random.Random(seed)
        self.num_arms = num_arms
        
        # Each arm has a hidden reward probability
        self.arm_probabilities = [self._rng.uniform(0.1, 0.9) for _ in range(num_arms)]
        
        # Best arm
        self.best_arm = max(range(num_arms), key=lambda i: self.arm_probabilities[i])
        
        # State
        self.total_pulls = 0
        self.max_pulls = 100
    
    def pull(self, arm: int) -> Dict[str, Any]:
        """Pull an arm and get reward."""
        self.total_pulls += 1
        
        # Get reward based on arm's probability
        success = self._rng.random() < self.arm_probabilities[arm]
        reward = 1.0 if success else 0.0
        
        return {
            "success": success,
            "reward": reward,
            "arm": arm,
            "true_probability": self.arm_probabilities[arm],
        }
    
    def is_done(self) -> bool:
        return self.total_pulls >= self.max_pulls
    
    def get_optimal_reward(self) -> float:
        """Get reward if always pulling best arm."""
        return self.arm_probabilities[self.best_arm]


class BanditAgent:
    """Agent that learns which arm to pull."""
    
    def __init__(self, use_memory=True, use_emotions=True, use_exploration=True):
        self.use_memory = use_memory
        self.use_emotions = use_emotions
        self.use_exploration = use_exploration
        
        if use_memory:
            self.memory = ContinualMemory()
        if use_emotions:
            self.emotions = AdaptiveEmotionSystem(learning_rate=0.4)
        
        # Arm statistics
        self.arm_pulls = {}
        self.arm_rewards = {}
        
        self.total_pulls = 0
        self.total_reward = 0.0
    
    def select_arm(self, num_arms: int) -> int:
        """Select which arm to pull."""
        # Initialize if needed
        for i in range(num_arms):
            if i not in self.arm_pulls:
                self.arm_pulls[i] = 0
                self.arm_rewards[i] = 0.0
        
        # Calculate scores for each arm
        scores = {}
        for i in range(num_arms):
            score = 0.5
            
            # Factor 1: Historical reward rate
            if self.arm_pulls[i] > 0:
                reward_rate = self.arm_rewards[i] / self.arm_pulls[i]
                score = reward_rate
            
            # Factor 2: Exploration bonus (if enabled)
            if self.use_exploration:
                # UCB1-style exploration
                total_pulls = sum(self.arm_pulls.values())
                if self.arm_pulls[i] == 0:
                    exploration_bonus = float('inf')  # Always explore untried arms
                else:
                    exploration_bonus = (2 * math.log(total_pulls) / self.arm_pulls[i]) ** 0.5
                score += exploration_bonus * 0.1
            
            # Factor 3: Memory boost
            if self.use_memory:
                similar = self.memory.search_similar(f"arm {i}", limit=5)
                if similar:
                    success_count = sum(1 for m in similar if isinstance(m.content, dict) and m.content.get("success"))
                    if success_count > len(similar) / 2:
                        score += 0.2
            
            # Factor 4: Emotion influence
            if self.use_emotions:
                frustration = self.emotions.get(EmotionType.FRUSTRATION)
                curiosity = self.emotions.get(EmotionType.CURIOSITY)
                
                # Frustrated: avoid recently failed arms
                if frustration > 0.5 and self.arm_pulls[i] > 0:
                    recent_rate = self.arm_rewards[i] / self.arm_pulls[i]
                    if recent_rate < 0.3:
                        score -= 0.3
                
                # Curious: explore more
                if curiosity > 0.6:
                    score += 0.1
            
            scores[i] = max(0.0, score)
        
        # Select best arm
        best_arm = max(scores, key=scores.get)
        return best_arm
    
    def process(self, arm: int, success: bool, reward: float):
        """Process experience."""
        self.total_pulls += 1
        self.total_reward += reward
        
        # Update arm statistics
        self.arm_pulls[arm] += 1
        self.arm_rewards[arm] += reward
        
        # Store in memory
        if self.use_memory:
            self.memory.store(MemoryEntry(
                memory_type=MemoryType.EPISODIC,
                content={"arm": arm, "success": success, "reward": reward},
                importance=0.6 if success else 0.3,
            ))
        
        # Update emotions
        if self.use_emotions:
            exp = Experience(success=success, reward=reward)
            self.emotions.update_from_experience(exp)
    
    def get_performance(self) -> Dict[str, float]:
        """Get performance metrics."""
        avg_reward = self.total_reward / max(1, self.total_pulls)
        
        # Calculate regret (difference from optimal)
        best_arm_rate = 0
        for i in range(len(self.arm_pulls)):
            if self.arm_pulls[i] > 0:
                rate = self.arm_rewards[i] / self.arm_pulls[i]
                if rate > best_arm_rate:
                    best_arm_rate = rate
        
        return {
            "avg_reward": avg_reward,
            "total_reward": self.total_reward,
            "total_pulls": self.total_pulls,
            "best_arm_rate": best_arm_rate,
        }


def run_test(config: Dict[str, bool], num_runs: int = 100, num_arms: int = 5) -> Dict[str, Any]:
    """Run test with given configuration."""
    all_rewards = []
    all_final_rates = []
    
    for seed in range(num_runs):
        env = BanditEnvironment(seed=seed, num_arms=num_arms)
        agent = BanditAgent(**config)
        
        while not env.is_done():
            arm = agent.select_arm(env.num_arms)
            result = env.pull(arm)
            agent.process(arm, result["success"], result["reward"])
        
        perf = agent.get_performance()
        all_rewards.append(perf["avg_reward"])
        all_final_rates.append(perf["best_arm_rate"])
    
    return {
        "avg_reward": statistics.mean(all_rewards),
        "std_reward": statistics.stdev(all_rewards) if len(all_rewards) > 1 else 0,
        "avg_best_rate": statistics.mean(all_final_rates),
        "std_best_rate": statistics.stdev(all_final_rates) if len(all_final_rates) > 1 else 0,
    }


def main():
    import math
    
    print("="*60)
    print("ABLATION STUDY — MULTI-ARMED BANDIT")
    print("="*60)
    print()
    print("Testing whether ARIA learns better than baseline.")
    print()
    
    num_runs = 100
    num_arms = 5
    
    configs = {
        "Full ARIA": {"use_memory": True, "use_emotions": True, "use_exploration": True},
        "No Memory": {"use_memory": False, "use_emotions": True, "use_exploration": True},
        "No Emotions": {"use_memory": True, "use_emotions": False, "use_exploration": True},
        "No Exploration": {"use_memory": True, "use_emotions": True, "use_exploration": False},
        "Baseline": {"use_memory": False, "use_emotions": False, "use_exploration": True},
    }
    
    all_results = {}
    for name, config in configs.items():
        print(f"Running: {name}...")
        results = run_test(config, num_runs, num_arms)
        all_results[name] = results
        print(f"  Avg Reward: {results['avg_reward']:.3f}")
        print(f"  Best Arm Rate: {results['avg_best_rate']:.1%}")
        print()
    
    # Print comparison table
    print("="*60)
    print("RESULTS")
    print("="*60)
    print()
    print(f"{'Configuration':<18} {'Avg Reward':>12} {'Best Arm %':>12}")
    print("-" * 45)
    
    for name, results in all_results.items():
        print(f"{name:<18} {results['avg_reward']:>11.3f} {results['avg_best_rate']:>11.1%}")
    
    print()
    print("="*60)
    print("ANALYSIS")
    print("="*60)
    print()
    
    full = all_results["Full ARIA"]
    baseline = all_results["Baseline"]
    
    reward_improvement = (full["avg_reward"] - baseline["avg_reward"]) / max(baseline["avg_reward"], 0.01) * 100
    rate_improvement = full["avg_best_rate"] - baseline["avg_best_rate"]
    
    print(f"Full ARIA vs Baseline:")
    print(f"  Reward: {baseline['avg_reward']:.3f} → {full['avg_reward']:.3f} ({reward_improvement:+.1f}%)")
    print(f"  Best Arm: {baseline['avg_best_rate']:.1%} → {full['avg_best_rate']:.1%} ({rate_improvement:+.1%})")
    
    print()
    print("Component Contributions:")
    for name in ["No Memory", "No Emotions", "No Exploration"]:
        comp = all_results[name]
        reward_diff = full["avg_reward"] - comp["avg_reward"]
        rate_diff = full["avg_best_rate"] - comp["avg_best_rate"]
        print(f"  {name}: {reward_diff:+.3f} reward, {rate_diff:+.1%} best arm rate")
    
    # Save results
    output = {
        "parameters": {"num_runs": num_runs, "num_arms": num_arms},
        "results": all_results,
    }
    
    output_path = Path("ablation_study_results.json")
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
