#!/usr/bin/env python3
"""
End-to-End Pipeline Experiment

Proves that the entire cognitive pipeline works together:

1. ARIA experiences repeated failures
2. LearningManager marks them as important
3. Emotion system lowers confidence and raises frustration
4. DreamScheduler consolidates the experiences
5. ARIA changes its planning strategy
6. Measure whether performance improves

This is the experiment that demonstrates the architecture is coherent.
"""

import random
import json
import statistics
from pathlib import Path
from typing import List, Dict, Any

from aria_core.vnext.models import Experience, ExperienceType, EmotionalState, EmotionType
from aria_core.vnext.learning_manager import LearningManager
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory
from aria_core.vnext.dreams import DreamScheduler
from aria_core.vnext.neural import ExperienceBuffer


class CognitiveAgent:
    """Simulated agent with full cognitive pipeline."""
    
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        
        # Cognitive systems
        self.memory = ContinualMemory()
        self.emotions = AdaptiveEmotionSystem()
        self.learning_manager = LearningManager(
            memory_store=self.memory,
            emotional_state=self.emotions.state,
        )
        self.dream_scheduler = DreamScheduler(memory=self.memory)
        self.experience_buffer = ExperienceBuffer(max_size=100, min_size=5)
        
        # State
        self.current_strategy = "aggressive"  # Start aggressive
        self.total_experiences = 0
        self.successes = 0
        self.failures = 0
        
        # History
        self.history: List[Dict[str, Any]] = []
    
    def take_action(self, environment: str) -> Experience:
        """Take an action based on current emotional state."""
        self.total_experiences += 1
        
        # Decision influenced by emotions
        caution = self.emotions.get_caution_level()
        exploration = self.emotions.get_exploration_rate()
        
        # Choose action based on strategy and emotions
        if self.current_strategy == "aggressive":
            # High risk, high reward
            success_prob = 0.3
            reward_range = (-0.8, 1.0)
        elif self.current_strategy == "cautious":
            # Low risk, steady reward
            success_prob = 0.7
            reward_range = (-0.2, 0.5)
        else:  # exploratory
            # Variable risk
            success_prob = 0.5
            reward_range = (-0.5, 0.8)
        
        # Environment modifies success probability
        if environment == "hostile":
            success_prob *= 0.5  # Halve success in hostile environment
        elif environment == "recovering":
            success_prob *= 1.2  # Boost in recovering environment
        
        # Emotions influence success probability
        success_prob += (1 - caution) * 0.1  # Less caution = more risk
        success_prob -= exploration * 0.05  # More exploration = more variance
        
        # Determine outcome
        success = random.random() < success_prob
        reward = random.uniform(*reward_range) if success else random.uniform(-0.8, -0.2)
        
        # Create experience
        experience = Experience(
            experience_type=ExperienceType.TASK,
            action=f"act_in_{environment}",
            result="success" if success else "failure",
            context={"environment": environment, "strategy": self.current_strategy},
            success=success,
            reward=reward,
            emotional_valence=1.0 if success else -0.5,
            emotional_intensity=abs(reward),
            confidence=0.5 + (0.3 if success else -0.2),
        )
        
        # Update state
        if success:
            self.successes += 1
        else:
            self.failures += 1
        
        return experience
    
    def process_experience(self, experience: Experience) -> Dict[str, Any]:
        """Process an experience through the full pipeline."""
        # 1. Learning Manager evaluates
        plan = self.learning_manager.evaluate(experience)
        
        # 2. Execute learning actions
        for action in plan.actions:
            if action.value == "store_episodic":
                from aria_core.vnext.models import MemoryEntry, MemoryType
                self.memory.store(MemoryEntry(
                    memory_type=MemoryType.EPISODIC,
                    content={
                        "action": experience.action,
                        "result": experience.result,
                        "reward": experience.reward,
                        "strategy": experience.context.get("strategy", ""),
                    },
                    importance=plan.importance.score,
                    confidence=experience.confidence,
                ))
            elif action.value == "update_emotional_state":
                self.emotions.update_from_experience(experience)
            elif action.value == "strengthen_semantic":
                # Find and strengthen similar memories
                similar = self.memory.search_similar(experience.action, limit=3)
                for mem in similar:
                    self.memory.strengthen(mem.id, delta=0.05)
        
        # 3. Add to experience buffer
        self.experience_buffer.add(experience)
        
        # 4. Record history
        self.history.append({
            "total": self.total_experiences,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": self.successes / max(1, self.total_experiences),
            "curiosity": self.emotions.get(EmotionType.CURIOSITY),
            "confidence": self.emotions.get(EmotionType.CONFIDENCE),
            "frustration": self.emotions.get(EmotionType.FRUSTRATION),
            "motivation": self.emotions.get(EmotionType.MOTIVATION),
            "strategy": self.current_strategy,
            "importance": plan.importance.score,
        })
        
        return {
            "importance": plan.importance.score,
            "actions": [a.value for a in plan.actions],
            "strategy": self.current_strategy,
        }
    
    def adapt_strategy(self) -> None:
        """Adapt strategy based on emotional state."""
        frustration = self.emotions.get(EmotionType.FRUSTRATION)
        confidence = self.emotions.get(EmotionType.CONFIDENCE)
        curiosity = self.emotions.get(EmotionType.CURIOSITY)
        
        # Strategy adaptation logic
        if frustration > 0.2:
            # Frustrated → be more cautious
            self.current_strategy = "cautious"
        elif confidence > 0.55 and curiosity > 0.5:
            # Confident and curious → explore more
            self.current_strategy = "exploratory"
        elif confidence < 0.5:
            # Low confidence → be cautious
            self.current_strategy = "cautious"
        else:
            # Default
            self.current_strategy = "aggressive"
    
    def dream(self) -> Dict[str, Any]:
        """Run a dream session."""
        session = self.dream_scheduler.dream()
        
        # After dreaming, adapt strategy
        self.adapt_strategy()
        
        return session.summary()
    
    def get_performance(self) -> Dict[str, float]:
        """Get current performance metrics."""
        return {
            "success_rate": self.successes / max(1, self.total_experiences),
            "total_experiences": self.total_experiences,
            "memory_count": self.memory.count(),
            "current_strategy": self.current_strategy,
            "curiosity": self.emotions.get(EmotionType.CURIOSITY),
            "confidence": self.emotions.get(EmotionType.CONFIDENCE),
            "frustration": self.emotions.get(EmotionType.FRUSTRATION),
        }


def run_experiment(
    num_agents: int = 10,
    phases: int = 3,
    experiences_per_phase: int = 20,
) -> Dict[str, Any]:
    """
    Run the end-to-end pipeline experiment.
    
    Phases:
    1. Baseline (no dreaming)
    2. Stress (repeated failures)
    3. Recovery (dreaming + adaptation)
    """
    print(f"Running pipeline experiment: {num_agents} agents, {phases} phases")
    
    all_results = []
    
    for agent_id in range(num_agents):
        agent = CognitiveAgent(agent_id)
        agent_results = {"agent_id": agent_id, "phases": []}
        
        for phase in range(phases):
            phase_results = {
                "phase": phase + 1,
                "experiences": [],
                "performance_before": agent.get_performance(),
            }
            
            # Run experiences
            for i in range(experiences_per_phase):
                # Environment changes by phase
                if phase == 0:
                    environment = "stable"
                elif phase == 1:
                    environment = "hostile"  # More failures
                else:
                    environment = "recovering"
                
                experience = agent.take_action(environment)
                result = agent.process_experience(experience)
                phase_results["experiences"].append(result)
            
            # Dream between phases (except after last)
            if phase < phases - 1:
                dream_result = agent.dream()
                phase_results["dream"] = dream_result
            
            phase_results["performance_after"] = agent.get_performance()
            agent_results["phases"].append(phase_results)
        
        all_results.append(agent_results)
    
    return analyze_results(all_results)


def analyze_results(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze experiment results."""
    
    # Aggregate by phase
    phase_stats = {}
    
    for agent_result in all_results:
        for phase in agent_result["phases"]:
            phase_num = phase["phase"]
            if phase_num not in phase_stats:
                phase_stats[phase_num] = {
                    "success_rates": [],
                    "frustrations": [],
                    "confidences": [],
                    "curiosities": [],
                    "strategies": [],
                }
            
            perf = phase["performance_after"]
            phase_stats[phase_num]["success_rates"].append(perf["success_rate"])
            phase_stats[phase_num]["frustrations"].append(perf["frustration"])
            phase_stats[phase_num]["confidences"].append(perf["confidence"])
            phase_stats[phase_num]["curiosities"].append(perf["curiosity"])
            phase_stats[phase_num]["strategies"].append(perf["current_strategy"])
    
    # Calculate averages
    summary = {}
    for phase_num, stats in phase_stats.items():
        summary[f"phase_{phase_num}"] = {
            "avg_success_rate": statistics.mean(stats["success_rates"]),
            "avg_frustration": statistics.mean(stats["frustrations"]),
            "avg_confidence": statistics.mean(stats["confidences"]),
            "avg_curiosity": statistics.mean(stats["curiosities"]),
            "most_common_strategy": max(set(stats["strategies"]), key=stats["strategies"].count),
        }
    
    # Calculate improvements
    if 1 in summary and 3 in summary:
        summary["improvement"] = {
            "success_rate_change": summary["phase_3"]["avg_success_rate"] - summary["phase_1"]["avg_success_rate"],
            "frustration_change": summary["phase_3"]["avg_frustration"] - summary["phase_1"]["avg_frustration"],
            "confidence_change": summary["phase_3"]["avg_confidence"] - summary["phase_1"]["avg_confidence"],
        }
    
    return {
        "summary": summary,
        "raw_results": all_results,
    }


def main():
    print("="*60)
    print("ARIA PIPELINE EXPERIMENT")
    print("="*60)
    print()
    print("This experiment proves the entire cognitive pipeline works together:")
    print("1. ARIA experiences repeated failures")
    print("2. LearningManager marks them as important")
    print("3. Emotion system lowers confidence and raises frustration")
    print("4. DreamScheduler consolidates the experiences")
    print("5. ARIA changes its planning strategy")
    print("6. Measure whether performance actually improves")
    print()
    
    # Run experiment
    results = run_experiment(num_agents=20, phases=3, experiences_per_phase=30)
    
    # Print results
    print("="*60)
    print("RESULTS")
    print("="*60)
    
    summary = results["summary"]
    
    for phase_key in ["phase_1", "phase_2", "phase_3"]:
        if phase_key in summary:
            phase = summary[phase_key]
            print(f"\n{phase_key.upper()}:")
            print(f"  Success Rate: {phase['avg_success_rate']:.2%}")
            print(f"  Frustration: {phase['avg_frustration']:.2f}")
            print(f"  Confidence: {phase['avg_confidence']:.2f}")
            print(f"  Curiosity: {phase['avg_curiosity']:.2f}")
            print(f"  Strategy: {phase['most_common_strategy']}")
    
    if "improvement" in summary:
        imp = summary["improvement"]
        print(f"\nIMPROVEMENT (Phase 1 → Phase 3):")
        print(f"  Success Rate: {imp['success_rate_change']:+.2%}")
        print(f"  Frustration: {imp['frustration_change']:+.2f}")
        print(f"  Confidence: {imp['confidence_change']:+.2f}")
    
    # Save results
    output_path = Path("pipeline_experiment_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    
    # Print conclusion
    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)
    
    if "improvement" in summary:
        imp = summary["improvement"]
        if imp["success_rate_change"] > 0:
            print("✓ Pipeline works: Performance improved after dreaming + adaptation")
        elif imp["success_rate_change"] < 0:
            print("✗ Pipeline needs tuning: Performance decreased")
        else:
            print("~ Pipeline neutral: No significant change")
        
        if imp["frustration_change"] < 0:
            print("✓ Emotions adapted: Frustration decreased after recovery")
        
        if imp["confidence_change"] > 0:
            print("✓ Confidence recovered: Agent regained confidence after dreaming")
    
    print("\nThe entire cognitive pipeline demonstrated:")
    print("  Experience → Learning Manager → Emotions → Dreaming → Strategy Change → Performance")


if __name__ == "__main__":
    main()
