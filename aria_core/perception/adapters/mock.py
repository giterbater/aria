# aria_core/perception/adapters/mock.py
"""
Mock Adapter — for testing and development.

Provides configurable perception data without real sensors.
Useful for:
- Unit testing
- Development
- Simulation without real hardware
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
    PerceivedEvent,
)


class MockAdapter:
    """
    Configurable mock adapter for testing.
    
    Usage:
        adapter = MockAdapter()
        adapter.set_location(37.7749, -122.4194)
        adapter.add_agent("Alice", "human")
        adapter.add_resource(PerceptionResource.FOOD, 10.0)
        
        frame = adapter.get_current_perception()
    """
    
    def __init__(self):
        self._source_name = "mock"
        self._location: Optional[GeoLocation] = None
        self._environment_type: EnvironmentType = EnvironmentType.UNKNOWN
        self._agents: list[PerceivedAgent] = []
        self._objects: list[PerceivedObject] = []
        self._resources: list[PerceivedResource] = []
        self._weather: Optional[PerceivedWeather] = None
        self._terrain: Optional[PerceivedTerrain] = None
        self._events: list[PerceivedEvent] = []
        self._confidence: float = 0.8
        self._available: bool = True
    
    def set_location(self, lat: float, lon: float, accuracy: float = 0.9) -> None:
        """Set current location."""
        self._location = GeoLocation(
            latitude=lat,
            longitude=lon,
            accuracy=accuracy,
            source="mock",
        )
    
    def set_environment(self, env_type: EnvironmentType) -> None:
        """Set environment type."""
        self._environment_type = env_type
    
    def add_agent(self, name: str, agent_type: str = "human") -> None:
        """Add a perceived agent."""
        self._agents.append(PerceivedAgent(
            name=name,
            agent_type=agent_type,
            location=self._location,
            confidence=self._confidence,
        ))
    
    def add_resource(self, resource_type: PerceptionResource, quantity: float) -> None:
        """Add a perceived resource."""
        self._resources.append(PerceivedResource(
            resource_type=resource_type,
            quantity=quantity,
            confidence=self._confidence,
        ))
    
    def set_weather(
        self,
        condition: WeatherCondition = WeatherCondition.CLEAR,
        temperature: float = 20.0,
    ) -> None:
        """Set weather conditions."""
        self._weather = PerceivedWeather(
            condition=condition,
            temperature=temperature,
            confidence=self._confidence,
        )
    
    def set_terrain(
        self,
        terrain_type: TerrainType = TerrainType.GRASS,
        traversability: float = 0.8,
    ) -> None:
        """Set terrain type."""
        self._terrain = PerceivedTerrain(
            terrain_type=terrain_type,
            traversability=traversability,
            confidence=self._confidence,
        )
    
    def add_event(self, event_type: str, description: str, severity: float = 0.5) -> None:
        """Add a perceived event."""
        self._events.append(PerceivedEvent(
            event_type=event_type,
            description=description,
            location=self._location,
            severity=severity,
            confidence=self._confidence,
        ))
    
    def set_confidence(self, confidence: float) -> None:
        """Set perception confidence."""
        self._confidence = confidence
    
    def set_available(self, available: bool) -> None:
        """Set availability."""
        self._available = available
    
    def clear(self) -> None:
        """Clear all perceived data."""
        self._agents.clear()
        self._objects.clear()
        self._resources.clear()
        self._events.clear()
        self._weather = None
        self._terrain = None
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from mock data."""
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=self._environment_type,
            location=self._location,
            objects=self._objects.copy(),
            agents=self._agents.copy(),
            resources=self._resources.copy(),
            weather=self._weather,
            terrain=self._terrain,
            events=self._events.copy(),
            overall_confidence=self._confidence,
            completeness=0.9,
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get current location."""
        return self._location
    
    def is_available(self) -> bool:
        """Check if mock is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence."""
        return self._confidence
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
