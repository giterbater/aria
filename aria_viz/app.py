#!/usr/bin/env python3
"""
ARIA Live Visualization — Environment-Independent Cognitive Architecture
"""

from flask import Flask, render_template, jsonify, request
import json
import time
import threading
import random
import sys
from pathlib import Path
from typing import Dict, Any, List

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global state
state = {
    "running": False,
    "step": 0,
    "max_steps": 100,
    "maze": [],
    "agent_pos": [0, 0],
    "goal_pos": [7, 7],
    "resources": [],
    "score": 0,
    "thoughts": ["Ready to start."],
    "emotions": {"confidence": 0.7, "curiosity": 0.5, "frustration": 0.0, "motivation": 0.7},
    "memory": {"episodic": 0, "semantic": 0, "total": 0, "items": []},
    "performance": [],
    "visited": [],
    "solved": False,
}


class SimpleMaze:
    def __init__(self, size=8, seed=42):
        self._rng = random.Random(seed)
        self.size = size
        self.maze = [[0]*size for _ in range(size)]
        self.agent = [0, 0]
        self.goal = [size-1, size-1]
        self.resources = []
        self.score = 0
        self.steps = 0
        self.max_steps = size * size * 2
        self.visited = set()
        self.visited.add((0,0))
        
        # Add walls
        for i in range(size):
            for j in range(size):
                if [i,j] != self.agent and [i,j] != self.goal:
                    if self._rng.random() < 0.25:
                        self.maze[i][j] = 1
        
        # Add resources
        for _ in range(size):
            x, y = self._rng.randint(0, size-1), self._rng.randint(0, size-1)
            if self.maze[x][y] == 0 and [x,y] != self.agent and [x,y] != self.goal:
                self.resources.append({"pos": [x, y], "collected": False})
    
    def get_neighbors(self):
        x, y = self.agent
        neighbors = []
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < self.size and 0 <= ny < self.size and self.maze[nx][ny] == 0:
                neighbors.append((nx, ny))
        return neighbors
    
    def move(self, direction):
        x, y = self.agent
        moves = {"up": (-1,0), "down": (1,0), "left": (0,-1), "right": (0,1)}
        dx, dy = moves.get(direction, (0,0))
        nx, ny = x+dx, y+dy
        
        if not (0 <= nx < self.size and 0 <= ny < self.size):
            return False, "Wall"
        if self.maze[nx][ny] == 1:
            return False, "Wall"
        
        self.agent = [nx, ny]
        self.visited.add((nx, ny))
        self.steps += 1
        
        # Check resources
        for r in self.resources:
            if not r["collected"] and r["pos"] == [nx, ny]:
                r["collected"] = True
                self.score += 10
        
        # Check goal
        if self.agent == self.goal:
            self.score += 100
            return True, "Goal!"
        
        return True, "Moved"


# Import ARIA components
sys.path.insert(0, str(Path(__file__).parent.parent))
import sys

from aria_core.vnext.models import Experience, EmotionType
from aria_core.vnext.emotions import AdaptiveEmotionSystem
from aria_core.vnext.memory import ContinualMemory, MemoryEntry, MemoryType


class ARIA:
    def __init__(self):
        self.memory = ContinualMemory()
        self.emotions = AdaptiveEmotionSystem(learning_rate=0.4)
        self.direction_stats = {"up": [0,0], "down": [0,0], "left": [0,0], "right": [0,0]}
        self.total = 0
    
    def think(self, maze):
        thoughts = []
        x, y = maze.agent
        goal_dist = abs(x - maze.goal[0]) + abs(y - maze.goal[1])
        thoughts.append(f"At ({x},{y}), goal distance: {goal_dist}")
        
        neighbors = maze.get_neighbors()
        thoughts.append(f"{len(neighbors)} possible moves")
        
        # Check nearby resources
        for r in maze.resources:
            if not r["collected"]:
                dist = abs(r["pos"][0] - x) + abs(r["pos"][1] - y)
                if dist <= 2:
                    thoughts.append(f"Resource at distance {dist}")
                    break
        
        # Check memory
        similar = self.memory.search_similar(f"position {x} {y}", limit=3)
        if similar:
            thoughts.append(f"Remembered {len(similar)} similar situations")
        
        # Check emotions
        frustration = self.emotions.get(EmotionType.FRUSTRATION)
        if frustration > 0.4:
            thoughts.append("Frustrated - being extra careful")
        
        return thoughts
    
    def decide(self, maze):
        x, y = maze.agent
        neighbors = maze.get_neighbors()
        
        if not neighbors:
            return "down"
        
        best_dir = None
        best_score = -1
        
        for nx, ny in neighbors:
            # Determine direction
            if nx < x: d = "up"
            elif nx > x: d = "down"
            elif ny < y: d = "left"
            else: d = "right"
            
            score = 0.5
            
            # Goal proximity
            goal_dist = abs(nx - maze.goal[0]) + abs(ny - maze.goal[1])
            if goal_dist < abs(x - maze.goal[0]) + abs(y - maze.goal[1]):
                score += 0.3
            
            # Resource proximity
            for r in maze.resources:
                if not r["collected"]:
                    rdist = abs(nx - r["pos"][0]) + abs(ny - r["pos"][1])
                    if rdist <= 2:
                        score += 0.2
            
            # Historical success
            pulls, wins = self.direction_stats[d]
            if pulls > 0:
                rate = wins / pulls
                score += (rate - 0.5) * 0.4
            
            if score > best_score:
                best_score = score
                best_dir = d
        
        return best_dir or "down"
    
    def process(self, direction, success):
        self.total += 1
        self.direction_stats[direction][0] += 1
        if success:
            self.direction_stats[direction][1] += 1
        
        self.memory.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content={"direction": direction, "success": success},
            importance=0.6 if success else 0.3,
        ))
        
        exp = Experience(success=success, reward=1.0 if success else -0.3)
        self.emotions.update_from_experience(exp)


maze_obj = None
aria_obj = None
sim_thread = None


def run_simulation():
    global state, maze_obj, aria_obj
    
    while state["running"] and not state["solved"]:
        # Think
        thoughts = aria_obj.think(maze_obj)
        state["thoughts"] = thoughts
        
        # Decide
        direction = aria_obj.decide(maze_obj)
        
        # Act
        success, msg = maze_obj.move(direction)
        
        # Process
        aria_obj.process(direction, success)
        
        # Update state
        state["step"] = maze_obj.steps
        state["agent_pos"] = maze_obj.agent
        state["score"] = maze_obj.score
        state["visited"] = list(maze_obj.visited)
        state["resources"] = maze_obj.resources
        state["emotions"] = {
            "confidence": aria_obj.emotions.get(EmotionType.CONFIDENCE),
            "curiosity": aria_obj.emotions.get(EmotionType.CURIOSITY),
            "frustration": aria_obj.emotions.get(EmotionType.FRUSTRATION),
            "motivation": aria_obj.emotions.get(EmotionType.MOTIVATION),
        }
        state["memory"]["total"] = aria_obj.memory.count()
        state["memory"]["episodic"] = aria_obj.memory.count(MemoryType.EPISODIC)
        
        state["performance"].append({"step": maze_obj.steps, "score": maze_obj.score})
        
        if success and msg == "Goal!":
            state["solved"] = True
            state["thoughts"] = ["SOLVED! Goal reached!"]
        elif maze_obj.steps >= maze_obj.max_steps:
            state["solved"] = True
            state["thoughts"] = ["Out of time."]
        
        time.sleep(0.4)
    
    state["running"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    return jsonify(state)


@app.route("/api/start", methods=["POST"])
def start():
    global state, maze_obj, aria_obj, sim_thread
    
    config = request.json or {}
    size = {"easy": 6, "medium": 8, "hard": 10}.get(config.get("difficulty", "medium"), 8)
    seed = config.get("seed", random.randint(0, 10000))
    
    maze_obj = SimpleMaze(size=size, seed=seed)
    aria_obj = ARIA()
    
    state.update({
        "running": True,
        "step": 0,
        "max_steps": maze_obj.max_steps,
        "maze": maze_obj.maze,
        "agent_pos": maze_obj.agent,
        "goal_pos": maze_obj.goal,
        "resources": maze_obj.resources,
        "score": 0,
        "thoughts": ["ARIA initialized. Starting exploration."],
        "emotions": {"confidence": 0.7, "curiosity": 0.5, "frustration": 0.0, "motivation": 0.7},
        "memory": {"episodic": 0, "semantic": 0, "total": 0, "items": []},
        "performance": [],
        "visited": [(0,0)],
        "solved": False,
    })
    
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()
    
    return jsonify({"status": "started"})


@app.route("/api/reset", methods=["POST"])
def reset():
    global state
    state.update({
        "running": False,
        "step": 0,
        "maze": [],
        "agent_pos": [0, 0],
        "resources": [],
        "score": 0,
        "thoughts": ["Ready to start."],
        "emotions": {"confidence": 0.7, "curiosity": 0.5, "frustration": 0.0, "motivation": 0.7},
        "memory": {"episodic": 0, "semantic": 0, "total": 0, "items": []},
        "performance": [],
        "visited": [],
        "solved": False,
    })
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    print("ARIA running at http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
