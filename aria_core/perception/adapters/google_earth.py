# aria_core/perception/adapters/google_earth.py
"""
Google Earth Adapter — virtual environment perception.

Provides:
- Satellite imagery context
- 3D terrain data
- Place recognition
- Landmark detection
- Geographic features

Uses provider-independent interface (not tightly coupled to Google APIs).
"""

from __future__ import annotations

import datetime
from typing import Optional, Protocol, runtime_checkable

from ..models import (
    PerceptionFrame,
    GeoLocation,
    EnvironmentType,
    TerrainType,
    PerceivedTerrain,
    PerceivedObject,
    ObjectType,
)


@runtime_checkable
class EarthDataProvider(Protocol):
    """Protocol for Earth data providers (Google, Bing, etc.)."""
    
    def get_elevation(self, lat: float, lon: float) -> float: ...
    def get_terrain_type(self, lat: float, lon: float) -> TerrainType: ...
    def get_satellite_imagery(self, lat: float, lon: float, zoom: int) -> Optional[bytes]: ...
    def get_places_nearby(self, lat: float, lon: float, radius_km: float) -> list[dict]: ...


class GoogleEarthAdapter:
    """
    Adapter for virtual environment perception.
    
    Usage:
        adapter = GoogleEarthAdapter()
        adapter.set_location(37.7749, -122.4194)
        
        frame = adapter.get_current_perception()
        # Frame contains terrain, landmarks, geographic features
    """
    
    def __init__(self, provider: Optional[EarthDataProvider] = None):
        self._source_name = "google_earth"
        self._provider = provider
        self._location: Optional[GeoLocation] = None
        self._elevation: float = 0.0
        self._terrain_type: TerrainType = TerrainType.UNKNOWN
        self._landmarks: list[dict] = []
        self._available: bool = True
    
    def set_location(self, lat: float, lon: float, accuracy: float = 0.9) -> None:
        """Set current location for Earth data lookup."""
        self._location = GeoLocation(
            latitude=lat,
            longitude=lon,
            accuracy=accuracy,
            source="google_earth",
        )
        
        # Fetch terrain data if provider available
        if self._provider:
            try:
                self._elevation = self._provider.get_elevation(lat, lon)
                self._terrain_type = self._provider.get_terrain_type(lat, lon)
                self._landmarks = self._provider.get_places_nearby(lat, lon, 1.0)
            except Exception:
                pass
    
    def get_current_perception(self) -> PerceptionFrame:
        """Get perception frame from Google Earth data."""
        if self._location is None:
            return PerceptionFrame(
                source=self._source_name,
                environment_type=EnvironmentType.UNKNOWN,
                overall_confidence=0.0,
                completeness=0.1,
            )
        
        # Determine environment type from terrain
        env_type = self._terrain_to_environment(self._terrain_type)
        
        # Build terrain perception
        terrain = PerceivedTerrain(
            terrain_type=self._terrain_type,
            traversability=self._estimate_traversability(self._terrain_type),
            elevation=self._elevation,
            confidence=0.8 if self._provider else 0.5,
        )
        
        # Build landmark objects
        objects = []
        for landmark in self._landmarks:
            objects.append(PerceivedObject(
                object_type=ObjectType.LANDMARK,
                name=landmark.get("name", "unknown"),
                location=GeoLocation(
                    latitude=landmark.get("lat", 0),
                    longitude=landmark.get("lon", 0),
                    accuracy=0.8,
                    source="google_earth",
                ),
                confidence=0.8,
            ))
        
        return PerceptionFrame(
            timestamp=datetime.datetime.now(),
            source=self._source_name,
            environment_type=env_type,
            location=self._location,
            objects=objects,
            terrain=terrain,
            overall_confidence=0.8 if self._provider else 0.4,
            completeness=0.6,
            raw_data={
                "elevation": self._elevation,
                "terrain_type": self._terrain_type.value,
                "landmark_count": len(self._landmarks),
            },
        )
    
    def get_location(self) -> Optional[GeoLocation]:
        """Get current location."""
        return self._location
    
    def is_available(self) -> bool:
        """Check if Google Earth data is available."""
        return self._available
    
    def get_confidence(self) -> float:
        """Get confidence in Earth data."""
        return 0.8 if self._provider else 0.4
    
    def get_source_name(self) -> str:
        """Return source name."""
        return self._source_name
    
    def get_elevation(self) -> float:
        """Get current elevation in meters."""
        return self._elevation
    
    def get_terrain_type(self) -> TerrainType:
        """Get current terrain type."""
        return self._terrain_type
    
    def get_landmarks(self) -> list[dict]:
        """Get nearby landmarks."""
        return self._landmarks
    
    def _terrain_to_environment(self, terrain: TerrainType) -> EnvironmentType:
        """Convert terrain type to environment type."""
        mapping = {
            TerrainType.URBAN: EnvironmentType.OUTDOOR,
            TerrainType.GRASS: EnvironmentType.OUTDOOR,
            TerrainType.FOREST: EnvironmentType.OUTDOOR,
            TerrainType.DESERT: EnvironmentType.OUTDOOR,
            TerrainType.MOUNTAIN: EnvironmentType.OUTDOOR,
            TerrainType.WATER: EnvironmentType.OUTDOOR,
            TerrainType.INDOOR: EnvironmentType.INDOOR,
        }
        return mapping.get(terrain, EnvironmentType.UNKNOWN)
    
    def _estimate_traversability(self, terrain: TerrainType) -> float:
        """Estimate how easy terrain is to traverse."""
        mapping = {
            TerrainType.URBAN: 0.9,
            TerrainType.GRASS: 0.8,
            TerrainType.FOREST: 0.5,
            TerrainType.DESERT: 0.6,
            TerrainType.MOUNTAIN: 0.3,
            TerrainType.WATER: 0.1,
            TerrainType.INDOOR: 0.9,
        }
        return mapping.get(terrain, 0.5)
