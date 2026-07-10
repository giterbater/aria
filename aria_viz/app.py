#!/usr/bin/env python3
"""
ARIA Live Visualization — Web UI for watching ARIA think.

Shows:
- Maze with agent movement
- Emotion bars
- Memory state
- Current thought
- Live updates
"""

from flask import Flask, render_template, jsonify, send_from_directory
import json
import time
import threading
from pathlib import Path

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global state
current_state = {
    "maze": [],
    "agent_pos": [0, 0],
    "goal_pos": [4, 4],
    "emotions": {
        "confidence": 0.7,
        "curiosity": 0.5,
        "frustration": 0.0,
        "motivation": 0.7,
    },
    "memory": {
        "episodic": 0,
        "semantic": 0,
        "total": 0,
    },
    "thoughts": [],
    "step": 0,
    "solved": False,
    "history": [],
}

# Import ARIA components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from run_aria_demo import MazeEnvironment, ARIADemoAgent


def init_state():
    """Initialize the visualization state."""
    global current_state
    
    env = MazeEnvironment(seed=42, size=8)
    current_state["maze"] = env.maze
    current_state["agent_pos"] = list(env.agent_pos)
    current_state["goal_pos"] = list(env.goal_pos)
    current_state["size"] = env.size
    current_state["visited"] = []
    
    return env


@app.route("/")
def index():
    """Serve the main visualization page."""
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    """Get current state as JSON."""
    return jsonify(current_state)


@app.route("/api/start")
def start_simulation():
    """Start or restart the simulation."""
    global current_state
    
    env = init_state()
    agent = ARIADemoAgent()
    
    current_state["thoughts"] = ["ARIA initialized. Ready to explore."]
    current_state["step"] = 0
    current_state["solved"] = False
    current_state["history"] = []
    
    # Run simulation in background
    def run():
        global current_state
        
        while not env.is_solved() and not env.is_failed():
            # Perceive
            perception = agent.perceive(env)
            
            # Generate hypotheses
            hypotheses = agent.generate_hypotheses(perception)
            
            # Select
            hypothesis = agent.select_hypothesis(hypotheses)
            
            # Add thought
            thought = f"Step {current_state['step'] + 1}: Moving {hypothesis['direction']} (confidence: {hypothesis['confidence']:.0%})"
            current_state["thoughts"].append(thought)
            if len(current_state["thoughts"]) > 5:
                current_state["thoughts"].pop(0)
            
            # Act
            experience = agent.act(hypothesis, env)
            
            # Process
            agent.process_experience(experience)
            
            # Update state
            current_state["agent_pos"] = list(env.agent_pos)
            current_state["visited"].append(list(env.agent_pos))
            current_state["step"] += 1
            
            # Update emotions
            emotions = agent.emotions.state
            current_state["emotions"] = {
                "confidence": emotions.confidence,
                "curiosity": emotions.curiosity,
                "frustration": emotions.frustration,
                "motivation": emotions.motivation,
            }
            
            # Update memory
            current_state["memory"] = {
                "episodic": agent.memory.count(),
                "semantic": 0,
                "total": agent.memory.count(),
            }
            
            # Dream every 10 steps
            if current_state["step"] % 10 == 0 and not env.is_solved():
                agent.dream()
                current_state["thoughts"].append("* Dreaming... *")
                if len(current_state["thoughts"]) > 5:
                    current_state["thoughts"].pop(0)
            
            # Record history
            current_state["history"].append({
                "step": current_state["step"],
                "pos": list(env.agent_pos),
                "success": experience.success,
                "emotion": dict(current_state["emotions"]),
            })
            
            time.sleep(0.5)  # Slow down for visualization
        
        # Done
        if env.is_solved():
            current_state["thoughts"].append(f"SOLVED in {current_state['step']} steps!")
            current_state["solved"] = True
        else:
            current_state["thoughts"].append("FAILED - ran out of steps")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    
    return jsonify({"status": "started"})


@app.route("/api/reset")
def reset_simulation():
    """Reset the simulation."""
    global current_state
    init_state()
    current_state["thoughts"] = ["Reset. Ready to explore."]
    current_state["step"] = 0
    current_state["solved"] = False
    current_state["history"] = []
    current_state["visited"] = []
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    # Create directories
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    
    print("Starting ARIA Live Visualization...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=False, port=5000)
