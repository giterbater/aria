# aria_core/perception/adapters/simulation.py
"""
Simulation Adapter — wraps ARIA World into the World Interface.

This adapter converts ARIA World simulation state into
PerceptionFrame objects. It demonstrates how existing simulations
can be used without changing ARIA Core cognition.
"""

from __future__ import annotations

import datetime
from typing import Optional

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
    ObjectType,
    ResourceType as PerceptionResource,
    WeatherCondition,
    TerrainType,
    PerceivedObject,
    PerceivedAgent,
    PerceivedResource,
    PerceivedWeather,
    PerceivedTerrain,
)


class SimulationAdapter:
    """
    Adapter that converts ARIA World state to PerceptionFrame.
    
    Usage:
        adapter = SimulationAdapter(world_engine)
        frame = adapter.get_current_perception()
        # frame is now a standard PerceptionFrame
    """
    
    def __init__(self, world_engine=None):
        self._world = world_engine
        self._source_name = "simulation"
    
    def get_current_perception(self) -> PerceptionFrame:
        """Convert current world state to PerceptionFrame."""
        if self._world is None:
            return self._empty_frame()
        
        # Get world state
        world_state = self._world.world_state
        
        # Convert agents
        agents = []
        for agent in self._world.get_alive_agents():
            pos = self._world._agent_positions.get(agent.state.id, {})
            agents.append(PerceivedAgent(
                id=agent.state.id,
                name=agent.state.name,
                agent_type="human",
                location=GeoLocation(
                    latitude=pos.get("y", 0.5),
                    longitude=pos.get("x", 0.5),
                    accuracy=0.9,
                    source="simulation",
                ),
                state={
                    "hunger": agent.state.needs.hunger,
                    "energy": agent.state.needs.energy,
                    "occupation": agent.state.occupation.value,
                    "happiness": agent.happiness(),
                },
                confidence=1.0,
            ))
        
        # Convert resources
        resources = []
        for res_type, quantity in world_state.resources.items():
            resources.append(PerceivedResource(
                resource_type=self._map_resource_type(res_type.value),
                quantity=quantity,
                confidence=1.0,
            ))
        
        # Convert terrain (simplified)
        terrain = PerceivedTerrain(
            terrain_type=TerrainType.GRASS,
            traversability=0.8,
            confidence=0.9,
        )
        
        # Convert weather (simplified - simulation doesn't have weather yet)
        weather = PerceivedWeather(
            condition=WeatherCondition.CLEAR,
            temperature=20.0,
            confidence=0.5,
        )
        
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=EnvironmentType.SIMULATION,
            location=GeoLocation(
                latitude=0.5,
                longitude=0.5,
                accuracy=1.0,
                source="simulation",
            ),
            agents=agents,
            resources=resources,
            weather=weather,
            terrain=terrain,
            overall_confidence=1.0,
            completeness=0.8,
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get current location (center of simulation)."""
        return GeoLocation(
            latitude=0.5,
            longitude=0.5,
            accuracy=1.0,
            source="simulation",
        )
    
    def is_available(self) -> bool:
        """Check if simulation is running."""
        return self._world is not None
    
    def get_confidence(self) -> float:
        """Simulation has perfect confidence."""
        return 1.0
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def _empty_frame(self) -> PerceptionFrame:
        """Return empty frame when no world is available."""
        return PerceptionFrame(
            source=self._source_name,
            environment_type=EnvironmentType.SIMULATION,
            overall_confidence=0.0,
            completeness=0.0,
        )
    
    def _map_resource_type(self, sim_type: str) -> PerceptionResource:
        """Map simulation resource type to perception resource type."""
        mapping = {
            "food": PerceptionResource.FOOD,
            "water": PerceptionResource.WATER,
            "wood": PerceptionResource.WOOD,
            "stone": PerceptionResource.STONE,
            "iron": PerceptionResource.IRON,
            "tools": PerceptionResource.TOOLS,
        }
        return mapping.get(sim_type, PerceptionResource.UNKNOWN)
