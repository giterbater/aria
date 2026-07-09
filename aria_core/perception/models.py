# aria_core/perception/models.py
"""
Typed perception models.

Every environment must expose identical information through these models.
ARIA Core consumes only these types — never raw sensor data.

Design principle: The cognition should remain unchanged regardless of
whether data came from simulation, Google Earth, Wi-Fi, camera, or robot.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EnvironmentType(str, Enum):
    """Types of environments ARIA can perceive."""
    SIMULATION = "simulation"
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    VIRTUAL = "virtual"  # Google Earth, Maps
    MIXED = "mixed"      # Both indoor and outdoor
    UNKNOWN = "unknown"


class ObjectType(str, Enum):
    """Types of objects that can be perceived."""
    AGENT = "agent"
    RESOURCE = "resource"
    BUILDING = "building"
    LANDMARK = "landmark"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    WEATHER = "weather"
    TERRAIN = "terrain"
    UNKNOWN = "unknown"


class ResourceType(str, Enum):
    """Resources that can be perceived."""
    FOOD = "food"
    WATER = "water"
    WOOD = "wood"
    STONE = "stone"
    IRON = "iron"
    TOOLS = "tools"
    ENERGY = "energy"
    SHELTER = "shelter"
    UNKNOWN = "unknown"


class WeatherCondition(str, Enum):
    """Weather conditions."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    STORM = "storm"
    FOG = "fog"
    UNKNOWN = "unknown"


class TerrainType(str, Enum):
    """Terrain types."""
    GRASS = "grass"
    FOREST = "forest"
    DESERT = "desert"
    MOUNTAIN = "mountain"
    WATER = "water"
    URBAN = "urban"
    INDOOR = "indoor"
    UNKNOWN = "unknown"


@dataclass
class GeoLocation:
    """Geographic location."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    accuracy: float = 1.0  # 0-1, higher = more accurate
    source: str = "unknown"  # "gps", "wifi", "ip", "simulation"


@dataclass
class PerceivedObject:
    """A single perceived object."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    object_type: ObjectType = ObjectType.UNKNOWN
    name: str = ""
    location: Optional[GeoLocation] = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5  # 0-1, how confident are we in this perception
    first_seen: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_seen: datetime.datetime = field(default_factory=datetime.datetime.now)
    observation_count: int = 1


@dataclass
class PerceivedAgent:
    """A perceived agent (human, animal, or other entity)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    agent_type: str = "unknown"  # "human", "animal", "robot"
    location: Optional[GeoLocation] = None
    state: dict[str, Any] = field(default_factory=dict)  # health, energy, etc.
    confidence: float = 0.5
    first_seen: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_seen: datetime.datetime = field(default_factory=datetime.datetime.now)


@dataclass
class PerceivedResource:
    """A perceived resource."""
    resource_type: ResourceType = ResourceType.UNKNOWN
    quantity: float = 0.0
    location: Optional[GeoLocation] = None
    confidence: float = 0.5
    depleted: bool = False


@dataclass
class PerceivedWeather:
    """Weather conditions."""
    condition: WeatherCondition = WeatherCondition.UNKNOWN
    temperature: float = 20.0  # Celsius
    wind_speed: float = 0.0  # km/h
    visibility: float = 1.0  # 0-1
    confidence: float = 0.5


@dataclass
class PerceivedTerrain:
    """Terrain information."""
    terrain_type: TerrainType = TerrainType.UNKNOWN
    traversability: float = 0.5  # 0-1, how easy to traverse
    elevation: float = 0.0  # meters
    confidence: float = 0.5


@dataclass
class PerceivedEvent:
    """A perceived event."""
    event_type: str = "unknown"
    description: str = ""
    location: Optional[GeoLocation] = None
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    severity: float = 0.5  # 0-1
    confidence: float = 0.5
    related_objects: list[str] = field(default_factory=list)  # object IDs


@dataclass
class PerceptionFrame:
    """
    A single frame of perception from any environment.
    
    This is the universal interface. Every environment adapter must
    produce PerceptionFrame objects. ARIA Core consumes only these.
    
    ARIA Core never knows whether this came from:
    - Simulation
    - Google Earth
    - Wi-Fi
    - Camera
    - Robot sensors
    - Internet
    """
    # Metadata
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    source: str = "unknown"  # "simulation", "wifi", "gps", "camera", etc.
    environment_type: EnvironmentType = EnvironmentType.UNKNOWN
    
    # Location
    location: Optional[GeoLocation] = None
    
    # Perceived entities
    objects: list[PerceivedObject] = field(default_factory=list)
    agents: list[PerceivedAgent] = field(default_factory=list)
    resources: list[PerceivedResource] = field(default_factory=list)
    
    # Environment conditions
    weather: Optional[PerceivedWeather] = None
    terrain: Optional[PerceivedTerrain] = None
    
    # Events
    events: list[PerceivedEvent] = field(default_factory=list)
    
    # Confidence and quality
    overall_confidence: float = 0.5  # 0-1
    completeness: float = 0.5  # 0-1, how complete is this perception
    
    # Raw data (optional, for debugging)
    raw_data: dict[str, Any] = field(default_factory=dict)
    
    def merge(self, other: PerceptionFrame) -> PerceptionFrame:
        """Merge two perception frames (e.g., from different sensors)."""
        return PerceptionFrame(
            timestamp=max(self.timestamp, other.timestamp),
            source=f"{self.source}+{other.source}",
            environment_type=self.environment_type if self.environment_type != EnvironmentType.UNKNOWN else other.environment_type,
            location=self.location or other.location,
            objects=self.objects + other.objects,
            agents=self.agents + other.agents,
            resources=self.resources + other.resources,
            weather=self.weather or other.weather,
            terrain=self.terrain or other.terrain,
            events=self.events + other.events,
            overall_confidence=(self.overall_confidence + other.overall_confidence) / 2,
            completeness=min(1.0, self.completeness + other.completeness),
        )


@dataclass
class PerceptionContext:
    """
    Aggregated perception context for reasoning.
    
    This is what ARIA Core consumes. It's a processed version of
    multiple PerceptionFrames, ready for reasoning.
    """
    # Current state
    current_location: Optional[GeoLocation] = None
    environment_type: EnvironmentType = EnvironmentType.UNKNOWN
    known_environment: bool = False  # Have we been here before?
    environment_confidence: float = 0.0
    
    # Entities
    nearby_agents: list[PerceivedAgent] = field(default_factory=list)
    nearby_objects: list[PerceivedObject] = field(default_factory=list)
    nearby_resources: list[PerceivedResource] = field(default_factory=list)
    
    # Conditions
    weather: Optional[PerceivedWeather] = None
    terrain: Optional[PerceivedTerrain] = None
    
    # Events
    recent_events: list[PerceivedEvent] = field(default_factory=list)
    
    # Spatial memory
    visited_locations: list[GeoLocation] = field(default_factory=list)
    known_wifi_networks: list[str] = field(default_factory=list)
    nearby_known_places: list[str] = field(default_factory=list)
    
    # Confidence
    overall_confidence: float = 0.5
    perception_age_seconds: float = 0.0  # How old is the perception?
    
    def to_reasoning_context(self) -> dict[str, Any]:
        """Convert to dict for reasoning engine consumption."""
        return {
            "location": {
                "latitude": self.current_location.latitude if self.current_location else 0,
                "longitude": self.current_location.longitude if self.current_location else 0,
                "known_environment": self.known_environment,
                "confidence": self.environment_confidence,
            },
            "environment": self.environment_type.value,
            "agents_nearby": len(self.nearby_agents),
            "objects_nearby": len(self.nearby_objects),
            "resources_nearby": len(self.nearby_resources),
            "weather": self.weather.condition.value if self.weather else "unknown",
            "terrain": self.terrain.terrain_type.value if self.terrain else "unknown",
            "recent_events": len(self.recent_events),
            "visited_count": len(self.visited_locations),
            "known_networks": len(self.known_wifi_networks),
            "confidence": self.overall_confidence,
            "perception_age": self.perception_age_seconds,
        }
