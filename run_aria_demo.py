#!/usr/bin/env python3
"""
ARIA Full Demo — Puzzle Solving with Cognitive Pipeline

Shows the complete cognitive pipeline in action:

1. ARIA perceives the environment
2. Generates hypotheses
3. Uses memory
4. Gets stuck
5. Emotion changes (confidence ↓ frustration ↑)
6. Sleeps (DreamScheduler)
7. Consolidates memory
8. Tries again
9. Solves the task

A person should be able to watch that happen.
"""

import random
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from aria_core.vnext.models import Experience, ExperienceType, EmotionType
from aria_core.vnext.learning_manager import LearningManager
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory, MemoryEntry, MemoryType
from aria_core.vnext.dreams import DreamScheduler


class MazeEnvironment:
    """A maze environment that requires learning."""
    
    def __init__(self, seed: int = 42, size: int = 5):
        self._rng = random.Random(seed)
        self.size = size
        
        # Generate maze with guaranteed path
        self.maze = self._generate_maze()
        
        # Agent position
        self.agent_pos = (0, 0)
        self.goal_pos = (size - 1, size - 1)
        
        # State
        self.steps = 0
        self.max_steps = size * size * 3
        self.solved = False
        self.visited: set = set()
        
        # History
        self.move_history: List[Dict[str, Any]] = []
    
    def _generate_maze(self) -> List[List[int]]:
        """Generate a maze with guaranteed path from start to goal."""
        # Start with all paths
        maze = [[0 for _ in range(self.size)] for _ in range(self.size)]
        
        # Create a guaranteed path first (right, then down)
        path = []
        x, y = 0, 0
        while x < self.size - 1 or y < self.size - 1:
            path.append((x, y))
            if x < self.size - 1 and (y == self.size - 1 or self._rng.random() < 0.6):
                x += 1
            else:
                y += 1
        path.append((self.size - 1, self.size - 1))
        
        # Mark path cells as safe
        path_set = set(path)
        
        # Add walls (20% chance) but not on the path
        for i in range(self.size):
            for j in range(self.size):
                if (i, j) not in path_set:
                    if self._rng.random() < 0.2:
                        maze[i][j] = 1
        
        return maze
    
    def perceive(self) -> Dict[str, Any]:
        """Get current perception."""
        x, y = self.agent_pos
        
        # Get visible neighbors
        neighbors = {}
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                cell_type = "path" if self.maze[nx][ny] == 0 else "wall"
                neighbors[f"({nx},{ny})"] = {
                    "type": cell_type,
                    "visited": (nx, ny) in self.visited,
                }
        
        # Distance to goal
        goal_distance = abs(x - self.goal_pos[0]) + abs(y - self.goal_pos[1])
        
        return {
            "position": self.agent_pos,
            "goal": self.goal_pos,
            "neighbors": neighbors,
            "goal_distance": goal_distance,
            "steps_remaining": self.max_steps - self.steps,
            "visited_count": len(self.visited),
            "solved": self.solved,
        }
    
    def move(self, direction: str) -> Dict[str, Any]:
        """Move in a direction."""
        x, y = self.agent_pos
        
        # Parse direction
        if direction == "up":
            nx, ny = x - 1, y
        elif direction == "down":
            nx, ny = x + 1, y
        elif direction == "left":
            nx, ny = x, y - 1
        elif direction == "right":
            nx, ny = x, y + 1
        else:
            return {"success": False, "message": f"Invalid direction: {direction}"}
        
        # Check bounds
        if not (0 <= nx < self.size and 0 <= ny < self.size):
            return {"success": False, "message": "Out of bounds"}
        
        # Check wall
        if self.maze[nx][ny] == 1:
            return {"success": False, "message": "Wall"}
        
        # Move
        self.agent_pos = (nx, ny)
        self.visited.add((nx, ny))
        self.steps += 1
        
        # Check goal
        if self.agent_pos == self.goal_pos:
            self.solved = True
            return {"success": True, "message": "Goal reached!"}
        
        # Check step limit
        if self.steps >= self.max_steps:
            return {"success": False, "message": "Out of steps"}
        
        return {"success": True, "message": f"Moved to ({nx}, {ny})"}
    
    def is_solved(self) -> bool:
        return self.solved
    
    def is_failed(self) -> bool:
        return self.steps >= self.max_steps and not self.solved


class ARIADemoAgent:
    """ARIA agent with full cognitive pipeline."""
    
    def __init__(self, agent_id: str = "ARIA"):
        self.agent_id = agent_id
        
        # Cognitive systems
        self.memory = ContinualMemory()
        self.emotions = AdaptiveEmotionSystem(
            learning_rate=0.3,
            decay_rate=0.05,
        )
        self.learning_manager = LearningManager(
            memory_store=self.memory,
            emotional_state=self.emotions.state,
        )
        self.dream_scheduler = DreamScheduler(memory=self.memory)
        
        # State
        self.hypotheses: List[Dict[str, Any]] = []
        self.current_hypothesis: Optional[str] = None
        self.dream_count = 0
        self.total_experiences = 0
        
        # Loop detection
        self.recent_positions: List[tuple] = []
        self.loop_threshold = 5
        
        # History for visualization
        self.history: List[Dict[str, Any]] = []
    
    def perceive(self, environment: MazeEnvironment) -> Dict[str, Any]:
        """Perceive the environment."""
        return environment.perceive()
    
    def generate_hypotheses(self, perception: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate hypotheses about which direction to move."""
        hypotheses = []
        
        # Check for loop detection
        position = perception["position"]
        is_in_loop = self._detect_loop(position)
        
        # Check memory for similar situations
        similar = self.memory.search_similar(f"position {position}", limit=10)
        
        # Analyze neighbors
        for neighbor_pos, info in perception["neighbors"].items():
            if info["type"] == "wall":
                continue  # Can't move through walls
            
            # Calculate confidence based on multiple factors
            confidence = 0.5
            
            # Factor 1: Is it visited? (lower confidence, but less if in loop)
            if info["visited"]:
                confidence -= 0.1 if is_in_loop else 0.2
            
            # Factor 2: Memory boost from similar experiences
            for mem in similar:
                if isinstance(mem.content, dict):
                    if mem.content.get("success") and mem.content.get("to") == neighbor_pos:
                        confidence += 0.3
                    elif not mem.content.get("success") and mem.content.get("to") == neighbor_pos:
                        confidence -= 0.2
            
            # Factor 3: Distance to goal
            neighbor_pos_clean = neighbor_pos.strip("()")
            nx, ny = map(int, neighbor_pos_clean.split(","))
            goal_distance = abs(nx - perception["goal"][0]) + abs(ny - perception["goal"][1])
            current_distance = perception["goal_distance"]
            
            if goal_distance < current_distance:
                confidence += 0.2  # Closer to goal
            elif goal_distance > current_distance:
                confidence -= 0.1  # Farther from goal
            
            # Factor 4: Loop detection - if in loop, prefer unvisited
            if is_in_loop and not info["visited"]:
                confidence += 0.3
            
            # Determine direction
            x, y = position
            if nx < x:
                direction = "up"
            elif nx > x:
                direction = "down"
            elif ny < y:
                direction = "left"
            else:
                direction = "right"
            
            hypotheses.append({
                "direction": direction,
                "target": neighbor_pos,
                "confidence": max(0.1, min(0.9, confidence)),
                "reason": f"Distance: {goal_distance}, Visited: {info['visited']}, Loop: {is_in_loop}",
            })
        
        # Sort by confidence
        hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
        
        return hypotheses
    
    def _detect_loop(self, position: tuple) -> bool:
        """Detect if agent is in a loop."""
        self.recent_positions.append(position)
        if len(self.recent_positions) > self.loop_threshold:
            self.recent_positions.pop(0)
        
        # Check if we've seen this position recently
        if len(self.recent_positions) >= 3:
            # Check if last 3 positions are the same or alternating
            last_3 = self.recent_positions[-3:]
            if len(set(last_3)) <= 2:
                return True
        
        return False
    
    def select_hypothesis(self, hypotheses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select which hypothesis to test."""
        if not hypotheses:
            return {"direction": "up", "confidence": 0.3, "reason": "No hypotheses"}
        
        # Use emotional state to influence selection
        curiosity = self.emotions.get(EmotionType.CURIOSITY)
        confidence = self.emotions.get(EmotionType.CONFIDENCE)
        frustration = self.emotions.get(EmotionType.FRUSTRATION)
        
        # High frustration → be more careful (pick highest confidence)
        if frustration > 0.4:
            return hypotheses[0]
        
        # High curiosity → explore (pick lower confidence)
        if curiosity > 0.6 and len(hypotheses) > 1:
            return hypotheses[len(hypotheses) // 2]  # Middle option
        
        # Default → pick highest confidence
        return hypotheses[0]
    
    def act(self, hypothesis: Dict[str, Any], environment: MazeEnvironment) -> Experience:
        """Take action based on hypothesis."""
        direction = hypothesis["direction"]
        result = environment.move(direction)
        
        self.total_experiences += 1
        
        # Create experience
        experience = Experience(
            experience_type=ExperienceType.TASK,
            action=f"move_{direction}",
            result="success" if result["success"] else "failure",
            context={
                "direction": direction,
                "target": hypothesis.get("target"),
                "from": str(environment.agent_pos),
                "confidence": hypothesis["confidence"],
            },
            success=result["success"],
            reward=1.0 if result["success"] else -0.3,
            emotional_valence=1.0 if result["success"] else -0.5,
            emotional_intensity=0.6 if result["success"] else 0.4,
            confidence=hypothesis["confidence"],
        )
        
        return experience
    
    def process_experience(self, experience: Experience) -> Dict[str, Any]:
        """Process experience through cognitive pipeline."""
        # 1. Learning Manager evaluates
        plan = self.learning_manager.evaluate(experience)
        
        # 2. Execute learning actions
        for action in plan.actions:
            if action.value == "store_episodic":
                self.memory.store(MemoryEntry(
                    memory_type=MemoryType.EPISODIC,
                    content={
                        "action": experience.action,
                        "result": experience.result,
                        "reward": experience.reward,
                        "direction": experience.context.get("direction"),
                        "from": experience.context.get("from"),
                        "to": experience.context.get("target"),
                    },
                    importance=plan.importance.score,
                    confidence=experience.confidence,
                ))
            elif action.value == "update_emotional_state":
                self.emotions.update_from_experience(experience)
        
        return {
            "importance": plan.importance.score,
            "actions": [a.value for a in plan.actions],
        }
    
    def dream(self) -> Dict[str, Any]:
        """Run a dream session."""
        self.dream_count += 1
        session = self.dream_scheduler.dream()
        return session.summary()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state for visualization."""
        return {
            "agent_id": self.agent_id,
            "emotions": {
                "curiosity": self.emotions.get(EmotionType.CURIOSITY),
                "confidence": self.emotions.get(EmotionType.CONFIDENCE),
                "frustration": self.emotions.get(EmotionType.FRUSTRATION),
                "motivation": self.emotions.get(EmotionType.MOTIVATION),
            },
            "memory": {
                "episodic": self.memory.count(MemoryType.EPISODIC),
                "semantic": self.memory.count(MemoryType.SEMANTIC),
                "total": self.memory.count(),
            },
            "dream_count": self.dream_count,
            "total_experiences": self.total_experiences,
            "current_hypothesis": self.current_hypothesis,
        }
    
    def record_history(self, episode: int, perception: Dict[str, Any], result: Dict[str, Any]):
        """Record history for visualization."""
        state = self.get_state()
        self.history.append({
            "episode": episode,
            "state": state,
            "perception": {
                "position": perception.get("position"),
                "goal_distance": perception.get("goal_distance"),
                "steps_remaining": perception.get("steps_remaining"),
            },
            "result": result,
        })


def run_demo(seed: int = 42, size: int = 5, max_episodes: int = 50) -> Dict[str, Any]:
    """Run the full ARIA demo."""
    print("="*60)
    print("ARIA COGNITIVE PIPELINE DEMO")
    print("="*60)
    print()
    
    agent = ARIADemoAgent()
    environment = MazeEnvironment(seed=seed, size=size)
    
    print(f"Agent: {agent.agent_id}")
    print(f"Task: Navigate a {size}x{size} maze to reach the goal")
    print(f"Start: (0, 0)")
    print(f"Goal: ({size-1}, {size-1})")
    print(f"Max steps: {environment.max_steps}")
    print()
    
    episode = 0
    while episode < max_episodes and not environment.is_solved() and not environment.is_failed():
        episode += 1
        print(f"--- Step {episode} ---")
        
        # 1. Perceive
        perception = agent.perceive(environment)
        print(f"Position: {perception['position']}")
        print(f"Distance to goal: {perception['goal_distance']}")
        print(f"Steps remaining: {perception['steps_remaining']}")
        
        # 2. Generate hypotheses
        hypotheses = agent.generate_hypotheses(perception)
        print(f"Hypotheses: {len(hypotheses)} options")
        
        # 3. Select hypothesis
        hypothesis = agent.select_hypothesis(hypotheses)
        agent.current_hypothesis = f"Move {hypothesis['direction']} (confidence: {hypothesis['confidence']:.2f})"
        print(f"Selected: {hypothesis['direction']} (confidence: {hypothesis['confidence']:.2f})")
        
        # 4. Act
        experience = agent.act(hypothesis, environment)
        print(f"Result: {experience.result}")
        
        # 5. Process experience
        learning_result = agent.process_experience(experience)
        
        # 6. Record history
        agent.record_history(episode, perception, {
            "success": experience.success,
            "direction": hypothesis["direction"],
            "importance": learning_result["importance"],
        })
        
        # 7. Check if we should dream
        if agent.total_experiences % 10 == 0 and not environment.is_solved():
            print(f"\n  * Dreaming... *")
            dream_result = agent.dream()
            print(f"  Dream: {dream_result['memories_replayed']} replayed, "
                  f"{dream_result['memories_consolidated']} consolidated")
        
        # Show emotional state
        state = agent.get_state()
        print(f"Emotions: confidence={state['emotions']['confidence']:.2f}, "
              f"frustration={state['emotions']['frustration']:.2f}, "
              f"curiosity={state['emotions']['curiosity']:.2f}")
        print()
    
    # Final result
    print("="*60)
    print("DEMO COMPLETE")
    print("="*60)
    
    if environment.is_solved():
        print(f"✓ SOLVED in {episode} steps!")
        print(f"  Final position: {environment.agent_pos}")
    else:
        print(f"✗ FAILED after {episode} steps")
        print(f"  Final position: {environment.agent_pos}")
        print(f"  Goal was: {environment.goal_pos}")
    
    # Final state
    final_state = agent.get_state()
    print(f"\nFinal State:")
    print(f"  Memory: {final_state['memory']['total']} entries")
    print(f"  Dreams: {final_state['dream_count']}")
    print(f"  Confidence: {final_state['emotions']['confidence']:.2f}")
    print(f"  Frustration: {final_state['emotions']['frustration']:.2f}")
    print(f"  Visited cells: {len(environment.visited)}")
    
    return {
        "solved": environment.is_solved(),
        "steps": episode,
        "final_position": environment.agent_pos,
        "goal_position": environment.goal_pos,
        "final_state": final_state,
        "visited_cells": len(environment.visited),
        "history": agent.history,
    }


def main():
    # Run multiple seeds for statistics
    results = []
    for seed in range(5):
        print(f"\n{'='*60}")
        print(f"RUN {seed + 1}/5")
        print(f"{'='*60}\n")
        result = run_demo(seed=seed, size=5, max_episodes=50)
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    solved_count = sum(1 for r in results if r["solved"])
    avg_steps = statistics.mean([r["steps"] for r in results])
    
    print(f"Solved: {solved_count}/5 ({solved_count/5*100:.0f}%)")
    print(f"Average steps: {avg_steps:.1f}")
    
    # Save results
    output_path = Path("demo_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    import statistics
    main()
