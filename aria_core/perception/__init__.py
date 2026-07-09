# aria_core/perception/__init__.py
"""
Perception Layer — generalized perception interface for ARIA.

Provides:
- Typed perception models (PerceptionFrame, PerceptionContext)
- World Interface protocol
- Environment adapters (Simulation, GPS, Wi-Fi, Mock, Google Earth, Camera, Internet)
- Sensor fusion
- Perception memory
- Context building
- Geospatial reasoning

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
from .geospatial import GeospatialReasoner

from .adapters import (
    SimulationAdapter,
    WiFiAdapter,
    GPSAdapter,
    MockAdapter,
    GoogleEarthAdapter,
    CameraAdapter,
    InternetAdapter,
)

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
    "GeospatialReasoner",
    
    # Adapters
    "SimulationAdapter",
    "WiFiAdapter",
    "GPSAdapter",
    "MockAdapter",
    "GoogleEarthAdapter",
    "CameraAdapter",
    "InternetAdapter",
]
