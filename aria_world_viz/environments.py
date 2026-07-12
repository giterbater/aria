"""
Environment API — the contract between ARIA and any world.

ARIA never knows what world it's in.
It only receives observations and sends actions.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class Environment(Protocol):
    """Every environment must implement this interface."""
    
    def observe(self) -> Dict[str, Any]: ...
    def act(self, action: Dict[str, Any]) -> Dict[str, Any]: ...
    def step(self) -> Dict[str, Any]: ...
    def reset(self) -> None: ...
    def reward(self) -> float: ...
    def is_done(self) -> bool: ...
    def get_state(self) -> Dict[str, Any]: ...


@dataclass
class AgentState:
    """State of an ARIA-controlled agent."""
    id: str
    x: float
    y: float
    goal_x: float
    goal_y: float
    speed: float = 1.0
    energy: float = 100.0
    cargo: Dict[str, int] = field(default_factory=dict)


class CityEnvironment:
    """
    A small city simulation.
    
    Features:
    - Roads and buildings
    - Population (NPCs moving around)
    - Weather system
    - Time of day
    - Resources
    - Traffic
    - Events
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.size = config.get("size", 50)
        self.seed = config.get("seed", 42)
        self._rng = random.Random(self.seed)
        
        # Time
        self.time_of_day = 0.0  # 0-24 hours
        self.day = 1
        self.tick_count = 0
        
        # Weather
        self.weather = "clear"
        self.temperature = 20.0
        self.wind_speed = 5.0
        
        # Map layers
        self.roads = self._generate_roads()
        self.buildings = self._generate_buildings()
        self.vegetation = self._generate_vegetation()
        
        # Population
        self.npcs: List[Dict[str, Any]] = []
        self._generate_npcs(config.get("population", 30))
        
        # ARIA agents
        self.agents: List[AgentState] = []
        
        # Resources
        self.resources = {
            "energy": 100.0,
            "water": 100.0,
            "food": 100.0,
            "materials": 50.0,
        }
        
        # Events
        self.events: List[Dict[str, Any]] = []
        self.event_log: List[Dict[str, Any]] = []
        
        # Traffic
        self.traffic_level = 0.3
        self.traffic_history: List[float] = []
        
        # Performance
        self.total_reward = 0.0
        self.steps_taken = 0
        self.goals_reached = 0
        
    def _generate_roads(self) -> List[Dict[str, Any]]:
        """Generate road network."""
        roads = []
        # Main horizontal road
        for x in range(0, self.size, 1):
            roads.append({"x1": x, "y1": self.size // 2, "x2": x + 1, "y2": self.size // 2, "type": "main"})
        # Main vertical road
        for y in range(0, self.size, 1):
            roads.append({"x1": self.size // 2, "y1": y, "x2": self.size // 2, "y2": y + 1, "type": "main"})
        # Secondary roads
        for i in range(3):
            pos = self.size // 4 * (i + 1)
            for x in range(0, self.size, 1):
                roads.append({"x1": x, "y1": pos, "x2": x + 1, "y2": pos, "type": "secondary"})
            for y in range(0, self.size, 1):
                roads.append({"x1": pos, "y1": y, "x2": pos, "y2": y + 1, "type": "secondary"})
        return roads
    
    def _generate_buildings(self) -> List[Dict[str, Any]]:
        """Generate buildings."""
        buildings = []
        building_types = ["residential", "commercial", "industrial", "hospital", "school", "park"]
        
        for _ in range(40):
            x = self._rng.randint(2, self.size - 3)
            y = self._rng.randint(2, self.size - 3)
            
            # Don't place on main roads
            if abs(x - self.size // 2) < 2 or abs(y - self.size // 2) < 2:
                continue
            
            btype = self._rng.choice(building_types)
            size = self._rng.randint(2, 4)
            
            buildings.append({
                "x": x, "y": y,
                "width": size, "height": size,
                "type": btype,
                "name": f"{btype.title()} {len(buildings) + 1}",
                "population": self._rng.randint(10, 100) if btype == "residential" else 0,
                "activity": self._rng.uniform(0.3, 1.0),
            })
        return buildings
    
    def _generate_vegetation(self) -> List[Dict[str, Any]]:
        """Generate parks and trees."""
        vegetation = []
        for _ in range(20):
            x = self._rng.randint(0, self.size - 1)
            y = self._rng.randint(0, self.size - 1)
            vegetation.append({
                "x": x, "y": y,
                "type": self._rng.choice(["tree", "park", "garden"]),
                "size": self._rng.uniform(0.5, 2.0),
            })
        return vegetation
    
    def _generate_npcs(self, count: int) -> None:
        """Generate NPC population."""
        for i in range(count):
            x = self._rng.uniform(0, self.size - 1)
            y = self._rng.uniform(0, self.size - 1)
            self.npcs.append({
                "id": f"npc_{i}",
                "x": x, "y": y,
                "target_x": self._rng.uniform(0, self.size - 1),
                "target_y": self._rng.uniform(0, self.size - 1),
                "speed": self._rng.uniform(0.1, 0.5),
                "activity": self._rng.choice(["walking", "working", "resting"]),
                "home_x": x, "home_y": y,
            })
    
    def add_agent(self, agent_id: str, start_x: float = 0, start_y: float = 0, goal_x: float = None, goal_y: float = None) -> AgentState:
        """Add an ARIA-controlled agent to the world."""
        if goal_x is None:
            goal_x = self.size - 1
        if goal_y is None:
            goal_y = self.size - 1
        
        agent = AgentState(
            id=agent_id,
            x=start_x, y=start_y,
            goal_x=goal_x, goal_y=goal_y,
        )
        self.agents.append(agent)
        return agent
    
    def observe(self) -> Dict[str, Any]:
        """Get current observation of the world."""
        # Time of day effects
        hour = self.time_of_day % 24
        is_night = hour < 6 or hour > 20
        is_rush_hour = (7 <= hour <= 9) or (16 <= hour <= 18)
        
        # Traffic based on time
        base_traffic = 0.3
        if is_rush_hour:
            base_traffic = 0.8
        elif is_night:
            base_traffic = 0.1
        self.traffic_level = base_traffic + self._rng.uniform(-0.1, 0.1)
        self.traffic_level = max(0, min(1, self.traffic_level))
        
        # Weather changes
        if self._rng.random() < 0.05:
            self.weather = self._rng.choice(["clear", "cloudy", "rain", "fog"])
            self.temperature = self._rng.uniform(10, 30)
            self.wind_speed = self._rng.uniform(0, 20)
        
        # NPC movement
        for npc in self.npcs:
            dx = npc["target_x"] - npc["x"]
            dy = npc["target_y"] - npc["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist < 0.5:
                # Pick new target
                if npc["activity"] == "walking":
                    npc["target_x"] = self._rng.uniform(0, self.size - 1)
                    npc["target_y"] = self._rng.uniform(0, self.size - 1)
                else:
                    npc["target_x"] = npc["home_x"]
                    npc["target_y"] = npc["home_y"]
                    npc["activity"] = self._rng.choice(["walking", "working", "resting"])
            else:
                # Move toward target
                speed = npc["speed"] * (0.5 if self.weather == "rain" else 1.0)
                npc["x"] += (dx / dist) * speed
                npc["y"] += (dy / dist) * speed
        
        # Resource consumption
        self.resources["energy"] = max(0, self.resources["energy"] - 0.1)
        self.resources["water"] = max(0, self.resources["water"] - 0.05)
        self.resources["food"] = max(0, self.resources["food"] - 0.08)
        
        # Random events
        if self._rng.random() < 0.02:
            event = self._generate_event()
            self.events.append(event)
            self.event_log.append(event)
        
        # Remove old events
        self.events = [e for e in self.events if e.get("active", True)]
        
        return {
            "time_of_day": self.time_of_day,
            "day": self.day,
            "weather": self.weather,
            "temperature": self.temperature,
            "wind_speed": self.wind_speed,
            "traffic_level": self.traffic_level,
            "resources": self.resources.copy(),
            "npc_count": len(self.npcs),
            "active_events": len(self.events),
            "recent_events": self.event_log[-5:],
            "buildings": len(self.buildings),
            "agents": [
                {"id": a.id, "x": a.x, "y": a.y, "energy": a.energy}
                for a in self.agents
            ],
        }
    
    def act(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action in the world."""
        action_type = action.get("type", "move")
        agent_id = action.get("agent_id", "aria_0")
        
        agent = None
        for a in self.agents:
            if a.id == agent_id:
                agent = a
                break
        
        if agent is None:
            return {"success": False, "message": "Agent not found"}
        
        if action_type == "move":
            dx = action.get("dx", 0)
            dy = action.get("dy", 0)
            speed = action.get("speed", 1.0)
            
            new_x = agent.x + dx * speed
            new_y = agent.y + dy * speed
            
            # Bounds check
            new_x = max(0, min(self.size - 1, new_x))
            new_y = max(0, min(self.size - 1, new_y))
            
            agent.x = new_x
            agent.y = new_y
            agent.energy = max(0, agent.energy - 0.5)
            
            return {"success": True, "position": (new_x, new_y)}
        
        elif action_type == "gather":
            resource = action.get("resource", "food")
            amount = action.get("amount", 10)
            
            # Check if near a building with resources
            for building in self.buildings:
                dist = math.sqrt((agent.x - building["x"]) ** 2 + (agent.y - building["y"]) ** 2)
                if dist < 3 and building["type"] in ["commercial", "industrial"]:
                    self.resources[resource] = min(100, self.resources.get(resource, 0) + amount)
                    return {"success": True, "resource": resource, "amount": amount}
            
            return {"success": False, "message": "No resources nearby"}
        
        elif action_type == "observe_area":
            radius = action.get("radius", 5)
            nearby_npcs = []
            for npc in self.npcs:
                dist = math.sqrt((agent.x - npc["x"]) ** 2 + (agent.y - npc["y"]) ** 2)
                if dist <= radius:
                    nearby_npcs.append(npc)
            
            return {
                "success": True,
                "npcs_in_area": len(nearby_npcs),
                "activities": [npc["activity"] for npc in nearby_npcs],
            }
        
        return {"success": False, "message": f"Unknown action: {action_type}"}
    
    def step(self) -> Dict[str, Any]:
        """Advance the world by one tick."""
        self.tick_count += 1
        self.time_of_day = (self.time_of_day + 0.5) % 24  # 30 min per tick
        
        if self.time_of_day < 0.5:
            self.day += 1
        
        # Update traffic history
        self.traffic_history.append(self.traffic_level)
        if len(self.traffic_history) > 100:
            self.traffic_history.pop(0)
        
        # Resource regeneration
        self.resources["energy"] = min(100, self.resources["energy"] + 0.2)
        self.resources["water"] = min(100, self.resources["water"] + 0.1)
        
        return self.observe()
    
    def reward(self) -> float:
        """Calculate current reward."""
        reward = 0.0
        
        # Bonus for agent reaching goal
        for agent in self.agents:
            dist = math.sqrt((agent.x - agent.goal_x) ** 2 + (agent.y - agent.goal_y) ** 2)
            if dist < 2:
                reward += 10.0
                self.goals_reached += 1
        
        # Penalty for low resources
        for resource, amount in self.resources.items():
            if amount < 20:
                reward -= 1.0
        
        # Bonus for successful observations
        reward += len(self.events) * 0.5
        
        self.total_reward += reward
        return reward
    
    def is_done(self) -> bool:
        """Check if simulation is done."""
        return self.tick_count >= 500
    
    def get_state(self) -> Dict[str, Any]:
        """Get full world state."""
        return {
            "time_of_day": self.time_of_day,
            "day": self.day,
            "tick": self.tick_count,
            "weather": self.weather,
            "temperature": self.temperature,
            "resources": self.resources,
            "npc_count": len(self.npcs),
            "traffic_level": self.traffic_level,
            "total_reward": self.total_reward,
            "goals_reached": self.goals_reached,
            "events_total": len(self.event_log),
        }
    
    def reset(self) -> None:
        """Reset the environment."""
        self.__init__({"size": self.size, "seed": self.seed + self.tick_count})
    
    def _generate_event(self) -> Dict[str, Any]:
        """Generate a random event."""
        event_types = [
            {"type": "traffic", "message": "Traffic congestion detected", "impact": "traffic"},
            {"type": "weather", "message": "Weather change incoming", "impact": "weather"},
            {"type": "resource", "message": "Resource shortage warning", "impact": "resources"},
            {"type": "social", "message": "Community gathering nearby", "impact": "social"},
            {"type": "emergency", "message": "Emergency response needed", "impact": "urgency"},
        ]
        
        event = self._rng.choice(event_types)
        return {
            **event,
            "x": self._rng.uniform(0, self.size - 1),
            "y": self._rng.uniform(0, self.size - 1),
            "time": self.time_of_day,
            "day": self.day,
            "active": True,
            "severity": self._rng.uniform(0.3, 1.0),
        }
