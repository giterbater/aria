"""
ARIA World Simulator — Flask server.

Connects:
- CityEnvironment (the world)
- CognitiveAgent (ARIA)
- Dashboard (the UI)
"""

from flask import Flask, render_template, jsonify, request
import threading
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__, template_folder="templates", static_folder="static")

# Global state
state = {
    "running": False,
    "environment": None,
    "agent": None,
    "tick": 0,
    "max_ticks": 500,
    "world": {},
    "agent_state": {},
    "thoughts": [],
    "emotions": {},
    "memory": {},
    "performance": [],
    "event_log": [],
}


def init_world():
    """Initialize the world and agent."""
    from environments import CityEnvironment
    from cognitive_agent import CognitiveAgent
    
    population = 30
    env = CityEnvironment({"size": 50, "seed": 42, "population": population})
    agent = CognitiveAgent("aria_0")
    
    # Add agent to world
    env.add_agent("aria_0", start_x=25, start_y=25, goal_x=45, goal_y=45)
    
    # Store in local variables, not in state (state is JSON-serialized)
    import builtins
    builtins._env = env
    builtins._agent = agent
    
    # Set initial state for UI
    state["world"] = {
        "size": env.size,
        "time_of_day": 0,
        "day": 1,
        "weather": "clear",
        "temperature": 20,
        "wind_speed": 5,
        "traffic_level": 0,
        "resources": dict(env.resources),
        "npcs": [],
        "buildings": [],
        "roads": [],
        "agents": [],
        "events": [],
    }
    
    return env, agent


def run_simulation():
    """Run the simulation loop."""
    import builtins
    env = builtins._env
    agent = builtins._agent
    
    while state["running"] and not env.is_done():
        # 1. Observe
        observation = env.observe()
        
        # 2. Think
        thought = agent.observe(observation)
        
        # 3. Decide
        action = agent.decide(observation)
        
        # 4. Act
        result = env.act(action)
        
        # 5. Get reward
        reward = env.reward()
        
        # 6. Learn
        agent.process_outcome(action, result, reward)
        
        # 7. Step world
        env.step()
        
        # Update state
        state["tick"] = env.tick_count
        state["world"] = {
            "size": env.size,
            "time_of_day": env.time_of_day,
            "day": env.day,
            "weather": env.weather,
            "temperature": env.temperature,
            "wind_speed": env.wind_speed,
            "traffic_level": env.traffic_level,
            "resources": env.resources,
            "npcs": [{"x": n["x"], "y": n["y"], "activity": n["activity"]} for n in env.npcs],
            "buildings": [{"x": b["x"], "y": b["y"], "type": b["type"], "name": b["name"]} for b in env.buildings],
            "roads": env.roads[:50],  # Limit for performance
            "agents": [{"id": a.id, "x": a.x, "y": a.y, "energy": a.energy} for a in env.agents],
            "events": [{"type": e["type"], "message": e["message"], "x": e["x"], "y": e["y"]} for e in env.events],
        }
        state["agent_state"] = agent.get_state()
        state["thoughts"] = [t for t in agent.thought_history[-5:]]
        state["emotions"] = agent.get_state()["emotions"]
        state["memory"] = agent.get_state()["memory"]
        state["performance"].append({
            "tick": env.tick_count,
            "reward": reward,
            "total_reward": env.total_reward,
            "success_rate": agent._get_success_rate(),
        })
        state["event_log"] = [
            {"type": e["type"], "message": e["message"], "time": e.get("time", 0)}
            for e in env.event_log[-10:]
        ]
        
        time.sleep(0.3)
    
    state["running"] = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    # Only return JSON-serializable data
    safe = {k: v for k, v in state.items() if k not in ("environment", "agent")}
    return jsonify(safe)


@app.route("/api/start", methods=["POST"])
def start():
    import builtins
    init_world()
    state["running"] = True
    state["tick"] = 0
    state["performance"] = []
    
    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()
    
    return jsonify({"status": "started"})


@app.route("/api/reset", methods=["POST"])
def reset():
    state.update({
        "running": False,
        "tick": 0,
        "world": {},
        "agent_state": {},
        "thoughts": [],
        "emotions": {},
        "memory": {},
        "performance": [],
        "event_log": [],
    })
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    print("ARIA World Simulator")
    print("Running at http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=5000)
