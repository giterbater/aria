"""
ARIA Cognitive Agent — works with ANY environment.

ARIA never knows what world it's in.
It only receives observations and decides actions.
"""

import random
import math
from typing import Any, Dict, List, Optional

from aria_core.vnext.models import Experience, EmotionType
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory, MemoryEntry, MemoryType


class CognitiveAgent:
    """
    ARIA agent that operates in any environment.
    
    The agent:
    1. Observes the world
    2. Thinks about what it sees
    3. Decides what to do
    4. Learns from the outcome
    """
    
    def __init__(self, agent_id: str = "aria_0"):
        self.agent_id = agent_id
        
        # Cognitive systems
        self.memory = ContinualMemory()
        self.emotions = AdaptiveEmotionSystem(learning_rate=0.4)
        
        # State
        self.total_actions = 0
        self.total_reward = 0.0
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        
        # Thought history
        self.thought_history: List[Dict[str, Any]] = []
        self.current_thought: Dict[str, Any] = {}
        
        # Learning
        self.action_stats: Dict[str, Dict[str, int]] = {}
        self.reward_history: List[float] = []
        
    def observe(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Process observation and generate thoughts."""
        thoughts = []
        
        # Analyze time
        time_of_day = observation.get("time_of_day", 0)
        hour = int(time_of_day)
        if hour < 6:
            thoughts.append("Night time - low activity expected")
        elif 7 <= hour <= 9:
            thoughts.append("Morning rush hour - traffic increasing")
        elif 16 <= hour <= 18:
            thoughts.append("Evening rush hour - traffic peak")
        else:
            thoughts.append(f"Normal hours ({hour}:00)")
        
        # Analyze weather
        weather = observation.get("weather", "clear")
        if weather != "clear":
            thoughts.append(f"Weather: {weather} - may affect movement")
        
        # Analyze traffic
        traffic = observation.get("traffic_level", 0)
        if traffic > 0.7:
            thoughts.append("High traffic - consider alternative routes")
        elif traffic < 0.2:
            thoughts.append("Low traffic - good opportunity to move")
        
        # Analyze resources
        resources = observation.get("resources", {})
        low_resources = [r for r, v in resources.items() if v < 30]
        if low_resources:
            thoughts.append(f"Low resources: {', '.join(low_resources)}")
        
        # Check events
        events = observation.get("recent_events", [])
        if events:
            latest = events[-1]
            thoughts.append(f"Event: {latest.get('message', 'unknown')}")
        
        # Check memory for similar situations
        similar = self.memory.search_similar(
            f"weather {weather} traffic {traffic:.2f}",
            limit=3
        )
        if similar:
            thoughts.append(f"Recall: {len(similar)} similar past situations")
        
        # Check emotions
        frustration = self.emotions.get(EmotionType.FRUSTRATION)
        curiosity = self.emotions.get(EmotionType.CURIOSITY)
        
        if frustration > 0.5:
            thoughts.append("Frustrated - being extra cautious")
        if curiosity > 0.7:
            thoughts.append("Curious - exploring new areas")
        
        # Build thought object
        thought = {
            "type": "observation",
            "thoughts": thoughts,
            "observation": {
                "time": f"{hour}:00",
                "weather": weather,
                "traffic": f"{traffic:.0%}",
                "resources": {k: f"{v:.0f}" for k, v in resources.items()},
            },
        }
        
        self.current_thought = thought
        self.thought_history.append(thought)
        
        return thought
    
    def decide(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Decide what action to take."""
        thoughts = []
        
        # Get agent state
        agent_pos = None
        for agent in observation.get("agents", []):
            if agent["id"] == self.agent_id:
                agent_pos = (agent["x"], agent["y"])
                break
        
        if agent_pos is None:
            return {"type": "wait", "reason": "No agent found"}
        
        # Analyze situation
        traffic = observation.get("traffic_level", 0)
        weather = observation.get("weather", "clear")
        resources = observation.get("resources", {})
        
        # Decision logic
        best_action = None
        best_score = -1
        
        # Option 1: Move toward goal
        for agent in observation.get("agents", []):
            if agent["id"] == self.agent_id:
                # This would need goal info from the environment
                # For now, just explore
                pass
        
        # Option 2: Gather resources if low
        low_resource = None
        for resource, amount in resources.items():
            if amount < 40:
                low_resource = resource
                break
        
        if low_resource:
            thoughts.append(f"Need {low_resource} - searching for source")
            best_action = {"type": "gather", "resource": low_resource, "amount": 10}
            best_score = 0.8
        
        # Option 3: Observe area
        if best_action is None:
            thoughts.append("Observing surroundings")
            best_action = {"type": "observe_area", "radius": 5}
            best_score = 0.5
        
        # Option 4: Move based on traffic
        if best_action is None:
            if traffic > 0.6:
                thoughts.append("Avoiding traffic - moving to less congested area")
                best_action = {"type": "move", "dx": random.uniform(-1, 1), "dy": random.uniform(-1, 1), "speed": 0.5}
            else:
                thoughts.append("Moving to explore")
                best_action = {"type": "move", "dx": random.uniform(-1, 1), "dy": random.uniform(-1, 1), "speed": 1.0}
            best_score = 0.4
        
        # Build decision thought
        thought = {
            "type": "decision",
            "thoughts": thoughts,
            "action": best_action,
            "confidence": best_score,
        }
        
        self.current_thought = thought
        self.thought_history.append(thought)
        
        return best_action
    
    def process_outcome(self, action: Dict[str, Any], result: Dict[str, Any], reward: float):
        """Process the outcome of an action."""
        self.total_actions += 1
        self.total_reward += reward
        self.reward_history.append(reward)
        
        # Update action stats
        action_type = action.get("type", "unknown")
        if action_type not in self.action_stats:
            self.action_stats[action_type] = {"success": 0, "failure": 0}
        
        if result.get("success", False):
            self.action_stats[action_type]["success"] += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        else:
            self.action_stats[action_type]["failure"] += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
        
        # Store in memory
        self.memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content={
                "action": action,
                "result": result,
                "reward": reward,
                "success": result.get("success", False),
            },
            importance=0.6 if reward > 0 else 0.3,
        ))
        
        # Update emotions
        exp = Experience(
            success=result.get("success", False),
            reward=reward,
        )
        self.emotions.update_from_experience(exp)
        
        # Build learning thought
        thought = {
            "type": "learning",
            "thoughts": [
                f"Action: {action_type}",
                f"Result: {'Success' if result.get('success') else 'Failed'}",
                f"Reward: {reward:+.2f}",
                f"Memory: {self.memory.count()} total",
            ],
            "stats": {
                "total_actions": self.total_actions,
                "total_reward": self.total_reward,
                "success_rate": self._get_success_rate(),
            },
        }
        
        self.current_thought = thought
        self.thought_history.append(thought)
    
    def _get_success_rate(self) -> float:
        """Get overall success rate."""
        total = sum(s["success"] + s["failure"] for s in self.action_stats.values())
        successes = sum(s["success"] for s in self.action_stats.values())
        return successes / max(1, total)
    
    def get_state(self) -> Dict[str, Any]:
        """Get agent cognitive state."""
        return {
            "agent_id": self.agent_id,
            "emotions": {
                "confidence": self.emotions.get(EmotionType.CONFIDENCE),
                "curiosity": self.emotions.get(EmotionType.CURIOSITY),
                "frustration": self.emotions.get(EmotionType.FRUSTRATION),
                "motivation": self.emotions.get(EmotionType.MOTIVATION),
            },
            "memory": {
                "episodic": self.memory.count(MemoryType.EPISODIC),
                "semantic": self.memory.count(MemoryType.SEMANTIC),
                "total": self.memory.count(),
            },
            "stats": {
                "total_actions": self.total_actions,
                "total_reward": self.total_reward,
                "success_rate": self._get_success_rate(),
                "action_stats": self.action_stats,
            },
            "current_thought": self.current_thought,
            "thought_history": self.thought_history[-10:],
        }
