# aria_core/perception/__init__.py
"""
Perception Layer — generalized perception interface for ARIA.

Provides:
- Typed perception models (PerceptionFrame, PerceptionContext)
- World Interface protocol
- Environment adapters (Simulation, GPS, Wi-Fi, Mock)
- Sensor fusion
- Perception memory
- Context building

Design principle: ARIA Core never knows where data came from.
Cognition remains unchanged — only perception changes.
"""

from .models import (
    PerceptionFrame,
    PerceptionContext,
    GeoLocation,
    EnvironmentType,
    ObjectType,
    ResourceType,
    WeatherCondition,
    TerrainType,
    PerceivedObject,
    PerceivedAgent,
    PerceivedResource,
    PerceivedWeather,
    PerceivedTerrain,
    PerceivedEvent,
)

from .interfaces import (
    WorldInterface,
    SensorFusion,
    PerceptionMemory,
    ContextBuilder,
)

from .fusion import SimpleSensorFusion
from .memory import SimplePerceptionMemory
from .context_builder import SimpleContextBuilder

from .adapters.simulation import SimulationAdapter
from .adapters.wifi import WiFiAdapter
from .adapters.gps import GPSAdapter
from .adapters.mock import MockAdapter

__all__ = [
    # Models
    "PerceptionFrame",
    "PerceptionContext",
    "GeoLocation",
    "EnvironmentType",
    "ObjectType",
    "ResourceType",
    "WeatherCondition",
    "TerrainType",
    "PerceivedObject",
    "PerceivedAgent",
    "PerceivedResource",
    "PerceivedWeather",
    "PerceivedTerrain",
    "PerceivedEvent",
    
    # Interfaces
    "WorldInterface",
    "SensorFusion",
    "PerceptionMemory",
    "ContextBuilder",
    
    # Implementations
    "SimpleSensorFusion",
    "SimplePerceptionMemory",
    "SimpleContextBuilder",
    
    # Adapters
    "SimulationAdapter",
    "WiFiAdapter",
    "GPSAdapter",
    "MockAdapter",
]
